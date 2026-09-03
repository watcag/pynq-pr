# pynq-pr

Automated partial reconfiguration bitstream generation for PYNQ-compatible boards (Zynq-7000, Kria KV260).

## Install

```bash
git clone --recurse-submodules <repo-url> pynq-pr
cd pynq-pr
pip install -r requirements.txt
```

If you already cloned without `--recurse-submodules`:

```bash
git submodule update --init
pip install -r requirements.txt
```

## Usage

Write a YAML config that describes your design:

```yaml
project: my_project
board: z1                    # z1 or kv260

sources:
  - rtl/my_module.v

reconfigurable_partitions:
  - partition_name: rp0
    modules:
      - cell_name: config_a     # name used for the output bitstream: rp0_config_a.bit
        top: my_module          # RTL module name (must match the Verilog module declaration)
        parameters:             # RTL parameter names and values (must match the Verilog parameter declarations)
          COEFFICIENTS: 5       # e.g. for: module my_module #(parameter COEFFICIENTS = 1) ...
          PIPELINE_DEPTH: 2
      - cell_name: config_b
        top: my_module
        parameters:
          COEFFICIENTS: 3
          PIPELINE_DEPTH: 4

  - partition_name: rp1
    modules:
      - cell_name: config_c
        top: my_other_module
```

All paths are relative to the working directory:

```bash
pynq-pr validate -c pr.yaml          # check config and source paths
pynq-pr build -c pr.yaml             # synth -> impl -> bitstreams
pynq-pr build -c pr.yaml --force     # overwrite existing output directory
```

Output lands in `output/<project>/bits/`: one static bitstream (`<project>.bit`), one partial bitstream per module (`<partition>_<cell_name>.bit`), plus matching `.hwh` files.

### Optional YAML fields

| Field | Default | Description |
|-------|---------|-------------|
| `reconfiguration_method` | `pcap` | `pcap` or `icap`. |
| `defines` | none | Dict of Verilog `` `define `` values applied project-wide. |

### RTL interface requirements

Your RTL modules must match these port names to connect to the shipped block design:

- AXI-Stream in: `x_TDATA`, `x_TVALID`, `x_TREADY`, `x_TLAST`
- AXI-Stream out: `y_TDATA`, `y_TVALID`, `y_TREADY`, `y_TLAST`
- AXI-Lite slave: `s_axi_AXILiteS_*`
- Clock: `clk`, Reset: `rst_n`

## Supported Boards

| Board | Part | FPGA |
|-------|------|------|
| z1 | xc7z020clg400-1 | Zynq-7000 |
| kv260 | xck26-sfvc784-2LV-c | Kria KV260 |

## Reconfiguration Methods

- **pcap** (default): the PS reconfigures the FPGA over PCAP. Standard PYNQ flow.
- **icap**: the FPGA reconfigures itself over ICAP using the Versatile DPR infrastructure. No PS involvement at reconfiguration time.

## Examples

- **[Add/Sub](examples/add_sub/)**: three independent reconfigurable partitions, each with polynomial module variants.
- **[Vision](examples/vision/)**: two reconfigurable image filter partitions chained through an AXI-Stream switch, with four HLS-generated 3×3 kernels.
- **[Attention](examples/attention/)**: scaled dot-product attention computed by sequentially reconfiguring a single partition through QK matmul, softmax, and PV matmul stages.
