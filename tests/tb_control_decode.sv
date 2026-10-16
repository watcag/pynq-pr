`ifndef DUT_MODULE
`define DUT_MODULE crossbar_control_adapter_0
`endif
`ifndef CONTROL_BASE
`define CONTROL_BASE 32'h0
`endif
module tb;
reg clk=0; always #5 clk=~clk;
reg resetn=0;
reg [31:0] awaddr=0, araddr=0;
reg awvalid=0,wvalid=0,arvalid=0;
wire awready,wready,bvalid,arready,rvalid;
wire[1:0] bresp,rresp;
wire[31:0] rdata;
wire[63:0] mawaddr,maraddr;
wire[1:0] mawvalid,mwvalid,marvalid,mbready,mrready;
reg mbvalid=0,mrvalid=0,seenaw=0,seenw=0;
integer write_count=0,read_count=0;
`DUT_MODULE dut(.aclk(clk),.aresetn(resetn),
.s_axi_awaddr(awaddr),.s_axi_awprot(3'b0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
.s_axi_wdata(32'h1234),.s_axi_wstrb(4'hf),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(1'b1),
.s_axi_araddr(araddr),.s_axi_arprot(3'b0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(1'b1),
.m_axi_awaddr(mawaddr),.m_axi_awprot(),.m_axi_awvalid(mawvalid),.m_axi_awready({1'b0,!seenaw}),
.m_axi_wdata(),.m_axi_wstrb(),.m_axi_wvalid(mwvalid),.m_axi_wready({1'b0,!seenw}),
.m_axi_bresp(4'b0),.m_axi_bvalid({1'b0,mbvalid}),.m_axi_bready(mbready),
.m_axi_araddr(maraddr),.m_axi_arprot(),.m_axi_arvalid(marvalid),.m_axi_arready({1'b0,!mrvalid}),
.m_axi_rdata(64'h12345678),.m_axi_rresp(4'b0),.m_axi_rvalid({1'b0,mrvalid}),.m_axi_rready(mrready));
always @(posedge clk) if(resetn) begin
 if(mawvalid[1]||marvalid[1]) $fatal(1,"disabled port received address AW=%b W=%b AR=%b",mawvalid,mwvalid,marvalid);
 if(mawvalid[0]&&!seenaw) begin seenaw<=1; write_count<=write_count+1; end
 if(mwvalid[0]&&!seenw) seenw<=1;
 if(seenaw&&seenw) mbvalid<=1;
 if(mbvalid&&mbready[0]) begin mbvalid<=0;seenaw<=0;seenw<=0;end
 if(marvalid[0]&&!mrvalid) begin mrvalid<=1;read_count<=read_count+1;end
 if(mrvalid&&mrready[0]) mrvalid<=0;
end

task read_at(input[31:0] address,input[1:0] expected);
 integer before_count;
 begin
 before_count=read_count;
 @(negedge clk); araddr=address;arvalid=1;
 @(posedge clk);while(!arready)@(posedge clk);
 @(negedge clk);arvalid=0;
 @(posedge clk);while(!rvalid)@(posedge clk);
 if(rresp!==expected)$fatal(1,"read %h response %b expected %b",address,rresp,expected);
 if(expected==3&&read_count!=before_count)$fatal(1,"unmapped read reached peripheral");
 if(expected==0&&read_count!=before_count+1)$fatal(1,"valid read was not forwarded");
 end
endtask

task write_at(input[31:0] address,input[1:0] expected);
 integer before_count;
 begin
 before_count=write_count;
 @(negedge clk);awaddr=address;awvalid=1;wvalid=1;
 fork
 begin @(posedge clk);while(!awready)@(posedge clk);@(negedge clk);awvalid=0;end
 begin @(posedge clk);while(!wready)@(posedge clk);@(negedge clk);wvalid=0;end
 join
 @(posedge clk);while(!bvalid)@(posedge clk);
 if(bresp!==expected)$fatal(1,"write %h response %b expected %b",address,bresp,expected);
 if(expected==3&&write_count!=before_count)$fatal(1,"unmapped write reached peripheral");
 if(expected==0&&write_count!=before_count+1)$fatal(1,"valid write was not forwarded");
 end
endtask
initial begin
 repeat(5)@(negedge clk);resetn=1;repeat(5)@(negedge clk);
 read_at(`CONTROL_BASE,0);read_at(`CONTROL_BASE+32'h7c,0);write_at(`CONTROL_BASE,0);write_at(`CONTROL_BASE+32'h7c,0);
 read_at(`CONTROL_BASE+32'h80,3);read_at(`CONTROL_BASE+32'hfc,3);read_at(`CONTROL_BASE+32'hff,3);
 read_at(`CONTROL_BASE+32'h100,3);read_at(`CONTROL_BASE+32'h10000,3);
 write_at(`CONTROL_BASE+32'h80,3);write_at(`CONTROL_BASE+32'hfc,3);write_at(`CONTROL_BASE+32'hff,3);
 write_at(`CONTROL_BASE+32'h100,3);write_at(`CONTROL_BASE+32'h10000,3);
 $display("AXILITE_DECODE_PASS mapped=4 unmapped=10 no_alias=1");$finish;
end
initial begin #10000;$fatal(1,"timeout");end
endmodule
