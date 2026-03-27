module test #(
    parameter logic [2-1:0] NN = 3,
    parameter logic [4-1:0] AA = 8,
    parameter logic [8-1:0] BB =16,
    parameter logic [AA+BB-1:0] CC = AA-10
    +BB*123
) (
    input        logic                   clk                 ,
    input        logic                   resten              ,
    input        logic [AA-1:0]          a      [NN    ]     ,
    input        logic [BB-1:0]          aa     [NN    ]     ,

    intf.master                          iii                 ,
    intf.slave                           ooo                 ,

    input        op    [AA-1:0][BB-1:0]  fuck   [NN-1:0][CC] ,//asda
    input        op    [AA-1:0]          fuck1  [NN-1:0][CC] ,//asda
    input        op    [AA-1:0]          fuck2  [CC    ]     ,//asda
    input        op    [AA-1:0]          fuck3               ,//asda
       //asdjfjsdaf;
    output       logic [CC-1:0]          out    [NN    ]     //aklj;as
);

localparam       [AA+BB-1:0]  DD = CC;
localparam  op       YH = 4'd8;
parameter       XXXXXX = 1;
localparam logic [AA+BB-1:0] EE = DD;

//sdf;lsj
    logic     [EE1-1:0]        tmp_logic         [NN-1+3:0]     ;//sajio;fdjoasj
    logic     [EE2-1:0]        tmp1_wire         [NN-1  :0]     ;
    logic     [EE3-1:0][AA:5]  tmp2_reg          [NN-1  :0][NN] ;
//daf;sjklf

    logic                      a_l                              ;
    user_def    a_w                              ;
    user_def1 [NN-1:0]     a_w1   [EE2]                            ;
    logic                      a_r                              ;

    a_intf_if                  a_intf()                ;
    b_intf_if                  b_intf()                ;


    inst1 i_inst1(.a(tmp1_wire), .b(tmp1_wire));

genvar i;
generate
  for (i = NN; i < NN; ++i) begin : gen_instances
    always_ff @(posedge clk or negedge resten) begin
      if (resten == 1'b0) begin
        tmp[i] <= '0;
      end else begin
        tmp[i] <= a[i] + aa[i];
      end
    end
    assign out[i] = tmp[i];
    assign ooo[i] = iii[i];
  end
endgenerate


endmodule