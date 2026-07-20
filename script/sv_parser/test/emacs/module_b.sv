module module_b
#(
    parameter XX    =   16,
    parameter OO    =   8
)
(
    input clk,
    input reset,

    input   logic       [XX     -1:0]   xx,
    output  logic       [OO     -1:0]   oo,


    interface_b_cmd_if.master      b_a_cmd



);
endmodule
