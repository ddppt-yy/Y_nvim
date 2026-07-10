module top;
    logic       clk;
    logic [3:0] din;
    logic [3:0] dout;

    leaf u_leaf (
        /*AUTOINST*/
        // Outputs
        .dout                           (dout[3:0]),
        // Inputs
        .clk                            (clk),
        .din                            (din[3:0]));
endmodule

