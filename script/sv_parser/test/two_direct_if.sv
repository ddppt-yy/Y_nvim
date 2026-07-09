interface two_direct_if;
  import pkg_mthc_::*;
  logic [7:0] data;
  xxxx oooo;
  logic valid;
  logic ready;

  modport master (
    output data, valid, oooo,
    input ready,
    import send_data // 导入任务
  );
  modport slave (
    input data, valid,
    input oooo,
    output ready
  );

  task send_data(input logic [7:0] value);
    @(posedge ready);
    data = value;
    valid = 1;
    @(posedge ready);
    valid = 0;
  endtask
endinterface
