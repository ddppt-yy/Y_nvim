// adder8.sv - 8位加法器，寄存一拍输出
module adder8 (
    input  logic        clk,      // 时钟
    input  logic        rst_n,    // 低有效复位
    input  logic [7:0]  a,        // 输入A
    input  logic [7:0]  b,        // 输入B
    output logic [7:0]  sum       // 输出和（寄存器输出）
);

    // 内部寄存器
    logic [7:0] sum_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            sum_reg <= 8'h00;
        else
            sum_reg <= a + b;   // 组合加法，结果在下一拍输出
    end

    assign sum = sum_reg;

endmodule
