interface one_direct_if #(
    parameter logic [3:0] WIDTH = 8,
    parameter DEPTH = 8
    );
  logic [7:0] data;
  logic valid;
  logic ready;

  modport master (
    output data, valid,
    input ready
  );
  modport slave (
    input data, valid,
    output ready
  );
endinterface
