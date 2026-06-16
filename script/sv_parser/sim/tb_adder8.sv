// tb_adder8.sv - 加法器测试平台
module tb_adder8;

    logic        clk   = 0;
    logic        rst_n = 0;
    logic [7:0]  a     = 0;
    logic [7:0]  b     = 0;
    logic [7:0]  sum;

    adder8 u_dut (
        .clk   (clk),
        .rst_n (rst_n),
        .a     (a),
        .b     (b),
        .sum   (sum)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("waveform.vcd");
        $dumpvars(0, tb_adder8);

        $display("===== 加法器测试开始 =====");
        $monitor("时间 = %t, a = %2d, b = %2d, sum = %2d (期望: %2d)",
                  $time, a, b, sum, a + b);

        rst_n = 0;
        #15;
        rst_n = 1;
        #5;

        a = 8'd10; b = 8'd20;
        #10;

        a = 8'd255; b = 8'd1;
        #10;

        // 随机数测试（无警告写法）
        repeat (5) begin
            a = 8'($urandom_range(0, 255));
            b = 8'($urandom_range(0, 255));
            #10;
        end

        a = 0; b = 0;
        #10;

        #20;
        $display("===== 测试完成 =====");
        $finish;
    end

endmodule
