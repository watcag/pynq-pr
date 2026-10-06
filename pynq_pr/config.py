import yaml
from pathlib import Path

VALID_RECONFIG_METHODS = ("pcap", "icap")
PKG_DIR = Path(__file__).parent


def load_config(config_path, root_dir=None):
    with open(config_path) as f:
        config = yaml.safe_load(f)
    root_dir = Path(root_dir) if root_dir else Path.cwd()
    validate(config, root_dir)
    apply_defaults(config, root_dir)
    return config


def validate(config, root_dir):
    required = ["project", "board", "reconfigurable_partitions"]
    for key in required:
        if key not in config:
            raise ValueError(f"Missing required key: {key}")

    method = config.get("reconfiguration_method", "pcap")
    if method not in VALID_RECONFIG_METHODS:
        raise ValueError(f"Invalid reconfiguration_method '{method}'. Valid: {list(VALID_RECONFIG_METHODS)}")

    partitions = config["reconfigurable_partitions"]
    if not 1 <= len(partitions) <= 4:
        raise ValueError(f"Number of partitions must be between 1 and 4, got {len(partitions)}")

    if "sources" not in config or not config["sources"]:
        raise ValueError("Missing required key: sources")

    seen_partitions = set()
    for part in partitions:
        if "partition_name" not in part:
            raise ValueError("Partition missing required key: partition_name")
        pname = part["partition_name"]
        if pname in seen_partitions:
            raise ValueError(f"Duplicate partition_name: {pname}")
        seen_partitions.add(pname)

        if "modules" not in part or not part["modules"]:
            raise ValueError(f"Partition '{pname}' must have at least one module")

        seen_cells = set()
        for rm in part["modules"]:
            for key in ["cell_name", "top"]:
                if key not in rm:
                    raise ValueError(f"Module in partition '{pname}' missing required key: {key}")
            if rm["cell_name"] in seen_cells:
                raise ValueError(f"Duplicate cell_name in partition '{pname}': {rm['cell_name']}")
            seen_cells.add(rm["cell_name"])

    width = config.get("stream_width", 32)
    if width not in (32, 64, 128, 256, 512, 1024):
        raise ValueError(f"stream_width must be 32, 64, 128, 256, 512 or 1024, got {width}")
    burst = config.get("dma_burst", 16)
    if burst not in (2, 4, 8, 16, 32, 64, 128, 256):
        raise ValueError(f"dma_burst must be a power of two from 2 to 256, got {burst}")

    streams = config.get("streams", 1)
    if streams not in (1, 2):
        raise ValueError(f"streams must be 1 or 2 (stream k uses HP<k>), got {streams}")
    if streams > 1 and (config.get("reconfiguration_method", "pcap") != "pcap" or config.get("axis_switch")):
        raise ValueError("streams: 2 needs pcap (ICAP fetches over HP1) and no axis_switch")

    regions = config.get("reconfigurable_regions")
    if regions is not None and (not isinstance(regions, list) or not all(isinstance(r, str) for r in regions)):
        raise ValueError("reconfigurable_regions must be a list of clock region names, e.g. [X0Y1, X1Y1]")

    for src in config["sources"]:
        if not (root_dir / src).exists():
            raise FileNotFoundError(f"Source not found: {root_dir / src}")


def apply_defaults(config, root_dir):
    method = config.get("reconfiguration_method", "pcap")
    config["reconfiguration_method"] = method
    config.setdefault("axis_switch", False)
    config.setdefault("_versatile_freq", 100)  # ICAP runs at 2x this frequency
    config.setdefault("data_freq", 100)        # MHz, PL clock of the RPs, DMAs and interconnects
    config.setdefault("stream_width", 32)      # RP AXI4-Stream TDATA bits
    config.setdefault("dma_burst", 16)         # AXI DMA max burst length (beats)
    config.setdefault("streams", 1)            # stream pairs per partition, each with its own DMA

    dummy_path = str(PKG_DIR / "rtl" / ("dummy.v" if config["streams"] == 1 else "dummy2.v"))
    if "sources" not in config:
        config["sources"] = []
    if dummy_path not in config["sources"]:
        config["sources"].append(dummy_path)
