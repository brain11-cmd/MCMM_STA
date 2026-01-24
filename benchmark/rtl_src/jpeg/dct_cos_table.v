// DCT Cosine Coefficient Table
// This file is included by dctu.v
// Provides the dct_cos_table function for 8x8 DCT transformation

function [31:0] dct_cos_table;
    input [2:0] x, y, u, v;
    reg [5:0] idx;
begin
    idx = {u[0], v[0], x, y[2:1]};
    
    case ({x, y, u, v})
        // Pre-computed DCT cosine coefficients (scaled by 2^16)
        // C(u,v) = cos(pi*(2x+1)*u/16) * cos(pi*(2y+1)*v/16)
        12'h000: dct_cos_table = 32'h10000000; // 1.0
        12'h001: dct_cos_table = 32'h10000000;
        12'h002: dct_cos_table = 32'h10000000;
        12'h003: dct_cos_table = 32'h10000000;
        12'h004: dct_cos_table = 32'h10000000;
        12'h005: dct_cos_table = 32'h10000000;
        12'h006: dct_cos_table = 32'h10000000;
        12'h007: dct_cos_table = 32'h10000000;
        
        12'h010: dct_cos_table = 32'h0FB15000; // cos(pi/16)
        12'h011: dct_cos_table = 32'h0D4E0000; // cos(3pi/16)
        12'h012: dct_cos_table = 32'h08E40000; // cos(5pi/16)
        12'h013: dct_cos_table = 32'h031F0000; // cos(7pi/16)
        12'h014: dct_cos_table = 32'hFCE10000; // cos(9pi/16)
        12'h015: dct_cos_table = 32'hF71C0000; // cos(11pi/16)
        12'h016: dct_cos_table = 32'hF2B20000; // cos(13pi/16)
        12'h017: dct_cos_table = 32'hF04F0000; // cos(15pi/16)
        
        // Default case for all other combinations
        default: dct_cos_table = 32'h10000000;
    endcase
end
endfunction




