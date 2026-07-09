//-------------------------------------------------------------------------------
// Created by           : MT
// Filename             : template.sv
// Author               : hai.yan
// Created On           : 2022-06-17 14:43
// Last Modified        : 2023-03-31 22:59
// Version              : v1.0
// Description          :
//
//
//-------------------------------------------------------------------------------
module XXXX
//********************
//parameter
//********************
//BLOCK_BEGIN
import abc_def::*;
#(
    parameter XX    =   XX,
    parameter XX    =   XX
)
//BLOCK_END
//********************
// IO
//********************
//BLOCK_BEGIN
(
    input   logic       [xx     -1:0]   clk,
    input   logic       [xx     -1:0]   resetn,

    output  logic       [xx     -1:0]   xx,
    output  logic                       xx
);
//BLOCK_END

//********************
// SIGNAL
//********************
//BLOCK_BEGIN

interface_a_rd_if       a_c_rd0();
interface_a_rd_if       a_c_rd1();
interface_a_rd_rtn_if   a_c_rd_rtn0();
interface_a_rd_rtn_if   a_c_rd_rtn1();
interface_a_wr_if       a_c_wr();
interface_b_cmd_if      b_a_cmd();


logic         [xx     -1:0]   xx;
logic         [xx     -1:0]   xx;
/*AUTOWIRE*/
/*AUTOREG*/

//BLOCK_END
//********************
// VAR
//********************
//BLOCK_BEGIN
    //genvar i;j;
    //integer i;j;
//BLOCK_END
//********************
// MAIN CODE
// 1.xxx
//      1.1xxx
//      1.2xxx
// 2.xxx
//********************
//BLOCK_BEGIN
//////////
// 1.xxx
//////////

/*instance_module AUTO_TEMPLATE(
                                  .clk            (clk),
                                  .resetn         (resetn),
                                  .\(.*\)         (\1[]),);*/

module_a        u_a0(
`ifdef SPU_NUM_1
                    .spu_num            (spu_num[`INS_NUM-1:0])
`endif
                    /*AUTOINST*/);

module_b        u_b(/*AUTOINST*/);

/*module_c AUTO_TEMPLATE(.a_c_rd             (a_c_rd@.slave),
                         .a_c_rd_rtn         (a_c_rd_rtn@.master),

);*/

module_c #(.BUS_WIDTH(8),.BUS_DEPTH(512),.BUS_ADDR(8)) u_c0(/*AUTOINST*/);

module_c #(.BUS_WIDTH(8),.BUS_DEPTH(512),.BUS_ADDR(8)) u_c1(/*AUTOINST*/);



//////////
// 2.xxx
//////////


//BLOCK_END
endmodule
// Local Variables:
// verilog-library-directories:(".")
// verilog-library-files:("")
// verilog-typedef-regexp: "*_t"
// verilog-library-flags:("+libext+.svh")
// End:
