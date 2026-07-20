module module_c
#(
    parameter BUS_WIDTH=8  ,
    parameter BUS_DEPTH=512,
    parameter BUS_ADDR =8
)
(
    input clk,
    input reset,

    interface_a_rd_if.slave             a_c_rd0         ,
    interface_a_rd_if.slave             a_c_rd1         ,
    interface_a_rd_rtn_if.master        a_c_rd_rtn0     ,
    interface_a_rd_rtn_if.master        a_c_rd_rtn1     ,
    interface_a_wr_if.slave             a_c_wr
);
endmodule
