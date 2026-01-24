// Generic IP stubs for missing hard macros / RAMs / cells.
// These modules are lightweight behavioral models so Yosys can synthesize
// designs without external hard macros. They are not cycle-accurate models.

module SyncSpRamBeNx64_00000008_00000100_0_2 (
    input         Clk_CI,
    input         Rst_RBI,
    input         CSel_SI,
    input         WrEn_SI,
    input  [7:0]  BEn_SI,
    input  [63:0] WrData_DI,
    input  [7:0]  Addr_DI,
    output reg [63:0] RdData_DO
);
    reg [63:0] mem [0:255];
    integer i;
    always @(posedge Clk_CI) begin
        if (CSel_SI) begin
            if (WrEn_SI) begin
                for (i = 0; i < 8; i = i + 1) begin
                    if (BEn_SI[i]) begin
                        mem[Addr_DI][i*8 +: 8] <= WrData_DI[i*8 +: 8];
                    end
                end
            end
            RdData_DO <= mem[Addr_DI];
        end
    end
endmodule

module SyncSpRamBeNx64_00000008_00000100_0_2_d44 (
    input         Clk_CI,
    input         Rst_RBI,
    input         CSel_SI,
    input         WrEn_SI,
    input  [7:0]  BEn_SI,
    input  [63:0] WrData_DI,
    input  [7:0]  Addr_DI,
    output [63:0] RdData_DO
);
    SyncSpRamBeNx64_00000008_00000100_0_2 ram (
        .Clk_CI(Clk_CI),
        .Rst_RBI(Rst_RBI),
        .CSel_SI(CSel_SI),
        .WrEn_SI(WrEn_SI),
        .BEn_SI(BEn_SI),
        .WrData_DI(WrData_DI),
        .Addr_DI(Addr_DI),
        .RdData_DO(RdData_DO)
    );
endmodule

module SyncSpRamBeNx64_00000008_00000100_0_2_d45 (
    input         Clk_CI,
    input         Rst_RBI,
    input         CSel_SI,
    input         WrEn_SI,
    input  [7:0]  BEn_SI,
    input  [63:0] WrData_DI,
    input  [7:0]  Addr_DI,
    output [63:0] RdData_DO
);
    SyncSpRamBeNx64_00000008_00000100_0_2 ram (
        .Clk_CI(Clk_CI),
        .Rst_RBI(Rst_RBI),
        .CSel_SI(CSel_SI),
        .WrEn_SI(WrEn_SI),
        .BEn_SI(BEn_SI),
        .WrData_DI(WrData_DI),
        .Addr_DI(Addr_DI),
        .RdData_DO(RdData_DO)
    );
endmodule

module limping_SyncSpRamBeNx64_00000008_00000100_0_2 (
    input         Clk_CI,
    input         Rst_RBI,
    input         CSel_SI,
    input         WrEn_SI,
    input  [7:0]  BEn_SI,
    input  [63:0] WrData_DI,
    input  [7:0]  Addr_DI,
    output [63:0] RdData_DO
);
    SyncSpRamBeNx64_00000008_00000100_0_2 ram (
        .Clk_CI(Clk_CI),
        .Rst_RBI(Rst_RBI),
        .CSel_SI(CSel_SI),
        .WrEn_SI(WrEn_SI),
        .BEn_SI(BEn_SI),
        .WrData_DI(WrData_DI),
        .Addr_DI(Addr_DI),
        .RdData_DO(RdData_DO)
    );
endmodule

module hard_mem_1rw_d512_w64_wrapper (
    input         clk_i,
    input         reset_i,
    input  [63:0] data_i,
    input  [8:0]  addr_i,
    input         v_i,
    input         w_i,
    output reg [63:0] data_o
);
    reg [63:0] mem [0:511];
    always @(posedge clk_i) begin
        if (v_i) begin
            if (w_i) begin
                mem[addr_i] <= data_i;
            end
            data_o <= mem[addr_i];
        end
    end
endmodule

module hard_mem_1rw_d256_w95_wrapper (
    input         clk_i,
    input         reset_i,
    input  [94:0] data_i,
    input  [7:0]  addr_i,
    input         v_i,
    input         w_i,
    output reg [94:0] data_o
);
    reg [94:0] mem [0:255];
    always @(posedge clk_i) begin
        if (v_i) begin
            if (w_i) begin
                mem[addr_i] <= data_i;
            end
            data_o <= mem[addr_i];
        end
    end
endmodule

module hard_mem_1rw_bit_mask_d64_w96_wrapper (
    input         clk_i,
    input         reset_i,
    input  [95:0] data_i,
    input  [5:0]  addr_i,
    input         v_i,
    input  [95:0] w_mask_i,
    input         w_i,
    output reg [95:0] data_o
);
    reg [95:0] mem [0:63];
    integer i;
    always @(posedge clk_i) begin
        if (v_i) begin
            if (w_i) begin
                for (i = 0; i < 96; i = i + 1) begin
                    if (w_mask_i[i]) begin
                        mem[addr_i][i] <= data_i[i];
                    end
                end
            end
            data_o <= mem[addr_i];
        end
    end
endmodule

module hard_mem_1rw_bit_mask_d64_w15_wrapper (
    input         clk_i,
    input         reset_i,
    input  [14:0] data_i,
    input  [5:0]  addr_i,
    input         v_i,
    input  [14:0] w_mask_i,
    input         w_i,
    output reg [14:0] data_o
);
    reg [14:0] mem [0:63];
    integer i;
    always @(posedge clk_i) begin
        if (v_i) begin
            if (w_i) begin
                for (i = 0; i < 15; i = i + 1) begin
                    if (w_mask_i[i]) begin
                        mem[addr_i][i] <= data_i[i];
                    end
                end
            end
            data_o <= mem[addr_i];
        end
    end
endmodule

module hard_mem_1rw_bit_mask_d64_w7_wrapper (
    input         clk_i,
    input         reset_i,
    input  [6:0]  data_i,
    input  [5:0]  addr_i,
    input         v_i,
    input  [6:0]  w_mask_i,
    input         w_i,
    output reg [6:0] data_o
);
    reg [6:0] mem [0:63];
    integer i;
    always @(posedge clk_i) begin
        if (v_i) begin
            if (w_i) begin
                for (i = 0; i < 7; i = i + 1) begin
                    if (w_mask_i[i]) begin
                        mem[addr_i][i] <= data_i[i];
                    end
                end
            end
            data_o <= mem[addr_i];
        end
    end
endmodule

module hard_mem_1rw_byte_mask_d512_w64_wrapper (
    input         clk_i,
    input         reset_i,
    input         v_i,
    input         w_i,
    input  [8:0]  addr_i,
    input  [63:0] data_i,
    input  [7:0]  write_mask_i,
    output reg [63:0] data_o
);
    reg [63:0] mem [0:511];
    integer i;
    always @(posedge clk_i) begin
        if (v_i) begin
            if (w_i) begin
                for (i = 0; i < 8; i = i + 1) begin
                    if (write_mask_i[i]) begin
                        mem[addr_i][i*8 +: 8] <= data_i[i*8 +: 8];
                    end
                end
            end
            data_o <= mem[addr_i];
        end
    end
endmodule

module mem_1rf_lg6_w80_bit (
    output reg [79:0] Q,
    input             CLK,
    input             CEN,
    input  [79:0]      WEN,
    input  [5:0]       A,
    input  [79:0]      D,
    input  [2:0]       EMA,
    input  [1:0]       EMAW,
    input             GWEN,
    input             RET1N
);
    reg [79:0] mem [0:63];
    integer i;
    always @(posedge CLK) begin
        if (!CEN) begin
            if (!GWEN) begin
                for (i = 0; i < 80; i = i + 1) begin
                    if (!WEN[i]) begin
                        mem[A][i] <= D[i];
                    end
                end
            end
            Q <= mem[A];
        end
    end
endmodule

module RAM32_1RW1R (
`ifdef USE_POWER_PINS
    input VPWR,
    input VGND,
`endif
    input  [4:0]  A0,
    input  [4:0]  A1,
    input         CLK,
    input  [63:0] Di0,
    output reg [63:0] Do0,
    output reg [63:0] Do1,
    input         EN0,
    input         EN1,
    input  [7:0]  WE0
);
    reg [63:0] mem [0:31];
    integer i;
    always @(posedge CLK) begin
        if (EN0) begin
            for (i = 0; i < 8; i = i + 1) begin
                if (WE0[i]) begin
                    mem[A0][i*8 +: 8] <= Di0[i*8 +: 8];
                end
            end
            Do0 <= mem[A0];
        end
        if (EN1) begin
            Do1 <= mem[A1];
        end
    end
endmodule

module fakeram7_256x32 (
    input         clk,
    input  [31:0] wd_in,
    input         ce_in,
    input         we_in,
    output reg [31:0] rd_out,
    input  [7:0]  addr_in
);
    reg [31:0] mem [0:255];
    always @(posedge clk) begin
        if (ce_in) begin
            if (we_in) begin
                mem[addr_in] <= wd_in;
            end
            rd_out <= mem[addr_in];
        end
    end
endmodule

module data_arrays_0_ext (
    input  [5:0]  RW0_addr,
    input         RW0_en,
    input         RW0_clk,
    input         RW0_wmode,
    input  [31:0] RW0_wdata,
    output reg [31:0] RW0_rdata,
    input  [3:0]  RW0_wmask
);
    reg [31:0] mem [0:63];
    integer i;
    always @(posedge RW0_clk) begin
        if (RW0_en) begin
            if (RW0_wmode) begin
                for (i = 0; i < 4; i = i + 1) begin
                    if (RW0_wmask[i]) begin
                        mem[RW0_addr][i*8 +: 8] <= RW0_wdata[i*8 +: 8];
                    end
                end
            end
            RW0_rdata <= mem[RW0_addr];
        end
    end
endmodule

module OPENROAD_CLKGATE (
    input  CK,
    input  E,
    output GCK
);
    assign GCK = CK & E;
endmodule

module ibex_wrapper (
`ifdef USE_POWER_PINS
    input VPWR,
    input VGND,
`endif
    input         HCLK,
    input         HRESETn,
    output [31:0] HADDR,
    input  [0:0]  HREADY,
    output [0:0]  HWRITE,
    output [1:0]  HTRANS,
    output [2:0]  HSIZE,
    output [31:0] HWDATA,
    input  [31:0] HRDATA,
    input         NMI,
    input         EXT_IRQ,
    input  [27:0] IRQ,
    input  [23:0] SYSTICKCLKDIV
);
    assign HADDR = 32'b0;
    assign HWRITE = 1'b0;
    assign HTRANS = 2'b0;
    assign HSIZE = 3'b0;
    assign HWDATA = 32'b0;
endmodule

module HAxp5_ASAP7_75t_R (
    input  A,
    input  B,
    output CON,
    output SN
);
    assign CON = A & B;
    assign SN = A ^ B;
endmodule
