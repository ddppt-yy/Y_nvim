module test (
    clk     ,
    resetn  ,

    in_data ,
    en      ,
    out_data
);

parameter   WIDTH       = 1             ;
parameter   INIT_VAL    = {WIDTH{1'b0}} ; 

input                       clk         ;
input                       resetn      ;

input   wire [WIDTH-1:0]    in_data     ;
input   wire                en          ;
output  reg  [WIDTH-1:0]    out_data    ;

always@(posedge clk or negedge resetn) begin
    if(!resetn)
        out_data <= INIT_VAL    ;
    else if(en)
        out_data <= in_data     ;
end

endmodule
