interface bus_if;
    logic [7:0] req_dat;
    logic       req_val;
    logic       rsp_rdy;
    modport drv (
        output req_dat,
        output req_val,
        input  rsp_rdy
    );
endinterface

