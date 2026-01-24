// Simple test design without buses
module simple_test (
    input clk,
    input rst,
    input a,
    input b,
    output reg q
);

    wire n1, n2;
    
    assign n1 = a & b;
    assign n2 = n1 | rst;
    
    always @(posedge clk) begin
        if (rst)
            q <= 1'b0;
        else
            q <= n2;
    end

endmodule

