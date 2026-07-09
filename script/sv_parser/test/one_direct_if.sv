interface one_direct_if #(
    parameter logic [3:0] WIDTH = 8,
    parameter DEPTH = 8
    );
  logic [7:0] data;
  logic valid;
  logic ready;

  modport aaa (
    output data, valid,
    input ready
  );
  modport bbb (
    input data, valid,
    output ready
  );
endinterface
