module mp_wrap (
    /*AUTOARG*/
   // Outputs
   m_req_val, m_req_dat,
   // Inputs
   m_rsp_rdy
   );
    bus_if vif();
    /*AUTOINOUTMODPORT("bus_if", "drv", "", "m_")*/
    // Beginning of automatic in/out/inouts (from modport)
    output logic [7:0]          m_req_dat;
    output logic                m_req_val;
    input logic                 m_rsp_rdy;
    // End of automatics
    /*AUTOASSIGNMODPORT("bus_if", "drv", "vif", "", "m_")*/
    // Beginning of automatic assignments from modport
    assign vif.req_dat = m_req_dat;
    assign vif.req_val = m_req_val;
    assign m_rsp_rdy = vif.rsp_rdy;
    // End of automatics
endmodule
