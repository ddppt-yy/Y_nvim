`define LOCAL_A
`define LOCAL_B(x)

module shell (
    /*AUTOARG*/dout, pad, clk, din);
    /*AUTOINOUTPARAM("ref_mod")*/
    // Beginning of automatic parameters (from specific module)
    parameter                   WIDTH;
    parameter                   DEPTH;
    // End of automatics
    /*AUTOINOUTMODULE("ref_mod")*/
    // Beginning of automatic in/out/inouts (from specific module)
    output logic [WIDTH-1:0]    dout;
    inout                       pad;
    input logic                 clk;
    input logic [WIDTH-1:0]     din;
    // End of automatics
    /*AUTOTIEOFF*/
    // Beginning of automatic tieoffs (for this module's unterminated outputs)
    assign dout = '0;
    // End of automatics
    wire _unused_ok = &{1'b0,
                        /*AUTOUNUSED*/
                        // Beginning of automatic unused inputs
                        clk,
                        din,
                        pad,
                        // End of automatics
                        1'b0};
    /*AUTOUNDEF*/
    // Beginning of automatic undefs
    `undef LOCAL_A
    `undef LOCAL_B
    // End of automatics
endmodule

