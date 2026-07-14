module top;
    logic       clk;
    logic [3:0] din;
    logic [3:0] dout;
    logic [3:0] q;
    logic       en;

    leaf u_leaf (.*);

    always @ (/*AUTOSENSE*/) begin
        if (en) begin
            q = din + dout;
        end
    end
endmodule
