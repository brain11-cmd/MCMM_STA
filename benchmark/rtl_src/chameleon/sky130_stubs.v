// Sky130 cell stubs for chameleon (to work with SAED32 library)
// These are behavioral models of sky130-specific cells

module sky130_fd_sc_hd__mux4_1(
    input  A0,
    input  A1,
    input  A2,
    input  A3,
    input  S0,
    input  S1,
    output X
);
    assign X = (S1 & S0) ? A3 : (S1 ? A2 : (S0 ? A1 : A0));
endmodule

module sky130_fd_sc_hd__mux2_1(
    input  A0,
    input  A1,
    input  S,
    output X
);
    assign X = S ? A1 : A0;
endmodule

module sky130_fd_sc_hd__dfxtp_1(
    input  D,
    input  CLK,
    output reg Q
);
    always @(posedge CLK) begin
        Q <= D;
    end
endmodule

module sky130_fd_sc_hd__dfrtp_1(
    input  D,
    input  CLK,
    input  RESET_B,
    output reg Q
);
    always @(posedge CLK or negedge RESET_B) begin
        if (!RESET_B) begin
            Q <= 1'b0;
        end else begin
            Q <= D;
        end
    end
endmodule

module sky130_fd_sc_hd__clkbuf_4(
    input  A,
    output X
);
    assign X = A;
endmodule

module sky130_fd_sc_hd__clkbuf_8(
    input  A,
    output X
);
    assign X = A;
endmodule

module sky130_fd_sc_hd__clkbuf_16(
    input  A,
    output X
);
    assign X = A;
endmodule

module sky130_fd_sc_hd__clkbuf_2(
    input  A,
    output X
);
    assign X = A;
endmodule

module sky130_fd_sc_hd__inv_1(
    input  A,
    output Y
);
    assign Y = ~A;
endmodule

module sky130_fd_sc_hd__inv_2(
    input  A,
    output Y
);
    assign Y = ~A;
endmodule

module sky130_fd_sc_hd__inv_4(
    input  A,
    output Y
);
    assign Y = ~A;
endmodule

module sky130_fd_sc_hd__and2_1(
    input  A,
    input  B,
    output X
);
    assign X = A & B;
endmodule

module sky130_fd_sc_hd__and2_2(
    input  A,
    input  B,
    output X
);
    assign X = A & B;
endmodule

module sky130_fd_sc_hd__and2_4(
    input  A,
    input  B,
    output X
);
    assign X = A & B;
endmodule

module sky130_fd_sc_hd__and2b_2(
    input  A_N,
    input  B,
    output X
);
    assign X = (~A_N) & B;
endmodule

module sky130_fd_sc_hd__and3_4(
    input  A,
    input  B,
    input  C,
    output X
);
    assign X = A & B & C;
endmodule

module sky130_fd_sc_hd__and3b_4(
    input  A_N,
    input  B,
    input  C,
    output X
);
    assign X = (~A_N) & B & C;
endmodule

module sky130_fd_sc_hd__and4_4(
    input  A,
    input  B,
    input  C,
    input  D,
    output X
);
    assign X = A & B & C & D;
endmodule

module sky130_fd_sc_hd__and4b_4(
    input  A_N,
    input  B,
    input  C,
    input  D,
    output X
);
    assign X = (~A_N) & B & C & D;
endmodule

module sky130_fd_sc_hd__and4bb_4(
    input  A_N,
    input  B_N,
    input  C,
    input  D,
    output X
);
    assign X = (~A_N) & (~B_N) & C & D;
endmodule

module sky130_fd_sc_hd__nor2_2(
    input  A,
    input  B,
    output Y
);
    assign Y = ~(A | B);
endmodule

module sky130_fd_sc_hd__nor3b_4(
    input  A,
    input  B,
    input  C_N,
    output Y
);
    assign Y = ~(A | B | (~C_N));
endmodule

module sky130_fd_sc_hd__nor4b_4(
    input  A,
    input  B,
    input  C,
    input  D_N,
    output Y
);
    assign Y = ~(A | B | C | (~D_N));
endmodule

module sky130_fd_sc_hd__nor4b_2(
    input  A,
    input  B,
    input  C,
    input  D_N,
    output Y
);
    assign Y = ~(A | B | C | (~D_N));
endmodule

module sky130_fd_sc_hd__ebufn_2(
    input  A,
    input  TE_B,
    output Z
);
    assign Z = TE_B ? 1'bz : A;
endmodule

module sky130_fd_sc_hd__ebufn_4(
    input  A,
    input  TE_B,
    output Z
);
    assign Z = TE_B ? 1'bz : A;
endmodule

module sky130_fd_sc_hd__dlclkp_1(
    input  CLK,
    input  GATE,
    output GCLK
);
    assign GCLK = CLK & GATE;
endmodule

module sky130_fd_sc_hd__conb_1(
    output LO,
    output HI
);
    assign LO = 1'b0;
    assign HI = 1'b1;
endmodule























