module top;
    logic       clk;
    logic [3:0] din;
    logic [3:0] dout;
    logic [3:0] q;
    logic       en;

    leaf u_leaf (.*,
                 // Outputs
                 .dout                  (dout[3:0]),
                 // Inputs
                 .clk                   (clk),
                 .din                   (din[3:0]));

    always @ (/*AUTOSENSE*/ or din or dout or en) begin
        if (en) begin
            q = din + dout;
        end
    end
endmodule

