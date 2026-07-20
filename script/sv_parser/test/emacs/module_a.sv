module module_a
`ifdef SPU_NUM_1
                    .spu_num            (spu_num[`INS_NUM-1:0])
`endif
(
    input clk,
    input reset,

    interface_a_rd_if.master      a_c_rd0       ,
    interface_a_rd_if.master      a_c_rd1       ,
    interface_a_rd_rtn_if.slave   a_c_rd_rtn0   ,
    interface_a_rd_rtn_if.slave   a_c_rd_rtn1   ,
    interface_a_wr_if.master      a_c_wr        ,
    interface_b_cmd_if.slave      b_a_cmd





);
endmodule
