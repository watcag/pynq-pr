// Inert placeholder defining the memory RP boundary; replaced by each real RM.
module dummy_memory #(parameter DATA_WIDTH=128, parameter CONTROL_ADDR_WIDTH=32) (
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF m_axi:s_axi_AXILiteS, ASSOCIATED_RESET rst_n" *) input wire clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 rst_n RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire rst_n,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4, ID_WIDTH 0" *) output wire [63:0] m_axi_awaddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWLEN" *) output wire [7:0] m_axi_awlen,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWSIZE" *) output wire [2:0] m_axi_awsize,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWBURST" *) output wire [1:0] m_axi_awburst,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWLOCK" *) output wire m_axi_awlock,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWCACHE" *) output wire [3:0] m_axi_awcache,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWPROT" *) output wire [2:0] m_axi_awprot,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWQOS" *) output wire [3:0] m_axi_awqos,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWVALID" *) output wire m_axi_awvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWREADY" *) input wire m_axi_awready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WDATA" *) output wire [DATA_WIDTH-1:0] m_axi_wdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WSTRB" *) output wire [DATA_WIDTH/8-1:0] m_axi_wstrb,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WLAST" *) output wire m_axi_wlast,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WVALID" *) output wire m_axi_wvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WREADY" *) input wire m_axi_wready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi BRESP" *) input wire [1:0] m_axi_bresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi BVALID" *) input wire m_axi_bvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi BREADY" *) output wire m_axi_bready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARADDR" *) output wire [63:0] m_axi_araddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARLEN" *) output wire [7:0] m_axi_arlen,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARSIZE" *) output wire [2:0] m_axi_arsize,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARBURST" *) output wire [1:0] m_axi_arburst,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARLOCK" *) output wire m_axi_arlock,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARCACHE" *) output wire [3:0] m_axi_arcache,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARPROT" *) output wire [2:0] m_axi_arprot,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARQOS" *) output wire [3:0] m_axi_arqos,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARVALID" *) output wire m_axi_arvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi ARREADY" *) input wire m_axi_arready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi RDATA" *) input wire [DATA_WIDTH-1:0] m_axi_rdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi RRESP" *) input wire [1:0] m_axi_rresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi RLAST" *) input wire m_axi_rlast,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi RVALID" *) input wire m_axi_rvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi RREADY" *) output wire m_axi_rready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE" *) input wire [CONTROL_ADDR_WIDTH-1:0] s_axi_AXILiteS_awaddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS AWVALID" *) input wire s_axi_AXILiteS_awvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS AWREADY" *) output wire s_axi_AXILiteS_awready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS WDATA" *) input wire [31:0] s_axi_AXILiteS_wdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS WSTRB" *) input wire [3:0] s_axi_AXILiteS_wstrb,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS WVALID" *) input wire s_axi_AXILiteS_wvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS WREADY" *) output wire s_axi_AXILiteS_wready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS BRESP" *) output wire [1:0] s_axi_AXILiteS_bresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS BVALID" *) output wire s_axi_AXILiteS_bvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS BREADY" *) input wire s_axi_AXILiteS_bready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS ARADDR" *) input wire [CONTROL_ADDR_WIDTH-1:0] s_axi_AXILiteS_araddr,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS ARVALID" *) input wire s_axi_AXILiteS_arvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS ARREADY" *) output wire s_axi_AXILiteS_arready,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS RDATA" *) output wire [31:0] s_axi_AXILiteS_rdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS RRESP" *) output wire [1:0] s_axi_AXILiteS_rresp,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS RVALID" *) output wire s_axi_AXILiteS_rvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi_AXILiteS RREADY" *) input wire s_axi_AXILiteS_rready
);
assign m_axi_awaddr = 0;
assign m_axi_awlen = 0;
assign m_axi_awsize = 0;
assign m_axi_awburst = 0;
assign m_axi_awlock = 0;
assign m_axi_awcache = 0;
assign m_axi_awprot = 0;
assign m_axi_awqos = 0;
assign m_axi_awvalid = 0;
assign m_axi_wdata = 0;
assign m_axi_wstrb = 0;
assign m_axi_wlast = 0;
assign m_axi_wvalid = 0;
assign m_axi_bready = 0;
assign m_axi_araddr = 0;
assign m_axi_arlen = 0;
assign m_axi_arsize = 0;
assign m_axi_arburst = 0;
assign m_axi_arlock = 0;
assign m_axi_arcache = 0;
assign m_axi_arprot = 0;
assign m_axi_arqos = 0;
assign m_axi_arvalid = 0;
assign m_axi_rready = 0;
assign s_axi_AXILiteS_awready = 0;
assign s_axi_AXILiteS_wready = 0;
assign s_axi_AXILiteS_bresp = 0;
assign s_axi_AXILiteS_bvalid = 0;
assign s_axi_AXILiteS_arready = 0;
assign s_axi_AXILiteS_rdata = 0;
assign s_axi_AXILiteS_rresp = 0;
assign s_axi_AXILiteS_rvalid = 0;
endmodule
