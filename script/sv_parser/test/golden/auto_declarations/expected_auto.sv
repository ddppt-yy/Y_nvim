module top (
    /*AUTOARG*/
   // Outputs
   dout,
   // Inouts
   pad,
   // Inputs
   din, clk
   );
    /*AUTOINPUT*/
    // Beginning of automatic inputs (from unused autoinst inputs)
    input logic                 clk; // To u_leaf of leaf
    input logic [3:0]           din; // To u_leaf of leaf
    // End of automatics
    /*AUTOOUTPUT*/
    // Beginning of automatic outputs (from unused autoinst outputs)
    output logic [3:0]          dout; // From u_leaf of leaf
    // End of automatics
    /*AUTOINOUT*/
    // Beginning of automatic inouts (from unused autoinst inouts)
    inout                       pad; // To/From u_leaf of leaf
    // End of automatics
    /*AUTOWIRE*/

    leaf u_leaf (
        /*AUTOINST*/
        // Outputs
        .dout                           (dout[3:0]),
        // Inouts
        .pad                            (pad),
        // Inputs
        .clk                            (clk),
        .din                            (din[3:0]));
endmodule

