module riscvsingle(
    input  logic        clk, reset,
    output logic [31:0] PC,
    input  logic [31:0] Instr,
    output logic        MemWrite,
    output logic [31:0] ALUResult, WriteData,
    input  logic [31:0] ReadData
);
logic ALUSrc, RegWrite, Jump, Zero, PCSrc;
logic [1:0] ResultSrc, ImmSrc;
logic [2:0] ALUControl;

controller c(Instr[6:0], Instr[14:12], Instr[30], Zero,
             ResultSrc, MemWrite, PCSrc,
             ALUSrc, RegWrite, Jump,
             ImmSrc, ALUControl);

datapath dp(clk, reset, ResultSrc, PCSrc,
            ALUSrc, RegWrite,
            ImmSrc, ALUControl,
            Zero, PC, Instr,
            ALUResult, WriteData, ReadData);
endmodule


module controller(
    input  logic [6:0] op,
    input  logic [2:0] funct3,
    input  logic       funct7b5,
    input  logic       Zero,
    output logic [1:0] ResultSrc,
    output logic       MemWrite,
    output logic       PCSrc, ALUSrc,
    output logic       RegWrite, Jump,
    output logic [1:0] ImmSrc,
    output logic [2:0] ALUControl
);
logic [1:0] ALUOp;
logic Branch;

maindec md(op, ResultSrc, MemWrite, Branch,
           ALUSrc, RegWrite, Jump, ImmSrc, ALUOp);

aludec ad(op[5], funct3, funct7b5, ALUOp, ALUControl);

assign PCSrc = (Branch & Zero) | Jump;
endmodule


module maindec(
    input  logic [6:0] op,
    output logic [1:0] ResultSrc,
    output logic       MemWrite,
    output logic       Branch, ALUSrc,
    output logic       RegWrite, Jump,
    output logic [1:0] ImmSrc,
    output logic [1:0] ALUOp
);
logic [10:0] controls;

assign {RegWrite, ImmSrc, ALUSrc, MemWrite,
        ResultSrc, Branch, ALUOp, Jump} = controls;

always_comb
case(op)
    7'b0000011: controls = 11'b1_00_1_0_01_0_00_0; // lw
    7'b0100011: controls = 11'b0_01_1_1_00_0_00_0; // sw
    7'b0110011: controls = 11'b1_xx_0_0_00_0_10_0; // R-type
    7'b1100011: controls = 11'b0_10_0_0_00_1_01_0; // beq
    7'b0010011: controls = 11'b1_00_1_0_00_0_10_0; // I-type ALU
    7'b1101111: controls = 11'b1_11_0_0_10_0_00_1; // jal
    default:    controls = 11'bx_xx_x_x_xx_x_xx_x;
endcase
endmodule


module aludec(
    input  logic opb5,
    input  logic [2:0] funct3,
    input  logic funct7b5,
    input  logic [1:0] ALUOp,
    output logic [2:0] ALUControl
);
logic RtypeSub;
assign RtypeSub = funct7b5 & opb5;

always_comb
case(ALUOp)
    2'b00: ALUControl = 3'b000;
    2'b01: ALUControl = 3'b001;
    default: case(funct3)
        3'b000: ALUControl = RtypeSub ? 3'b001 : 3'b000;
        3'b010: ALUControl = 3'b101;
        3'b110: ALUControl = 3'b011;
        3'b111: ALUControl = 3'b010;
        default: ALUControl = 3'bxxx;
    endcase
endcase
endmodule


module datapath(
    input  logic clk, reset,
    input  logic [1:0] ResultSrc,
    input  logic PCSrc, ALUSrc,
    input  logic RegWrite,
    input  logic [1:0] ImmSrc,
    input  logic [2:0] ALUControl,
    output logic Zero,
    output logic [31:0] PC,
    input  logic [31:0] Instr,
    output logic [31:0] ALUResult, WriteData,
    input  logic [31:0] ReadData
);
logic [31:0] PCNext, PCPlus4, PCTarget;
logic [31:0] ImmExt;
logic [31:0] SrcA, SrcB;
logic [31:0] Result;

flopr #(32) pcreg(clk, reset, PCNext, PC);
adder pcadd4(PC, 32'd4, PCPlus4);
adder pcaddbranch(PC, ImmExt, PCTarget);
mux2 #(32) pcmux(PCPlus4, PCTarget, PCSrc, PCNext);

regfile rf(clk, RegWrite, Instr[19:15], Instr[24:20],
           Instr[11:7], Result, SrcA, WriteData);

extend ext(Instr[31:7], ImmSrc, ImmExt);

mux2 #(32) srcbmux(WriteData, ImmExt, ALUSrc, SrcB);
alu u_alu(SrcA, SrcB, ALUControl, ALUResult, Zero);

mux3 #(32) resultmux(ALUResult, ReadData, PCPlus4,
                     ResultSrc, Result);
endmodule


module alu(
    input  logic [31:0] a, b,
    input  logic [2:0] ALUControl,
    output logic [31:0] result,
    output logic Zero
);
always_comb begin
    case(ALUControl)
        3'b000: result = a + b;
        3'b001: result = a - b;
        3'b010: result = a & b;
        3'b011: result = a | b;
        3'b101: result = ($signed(a) < $signed(b)) ? 32'd1 : 32'd0;
        default: result = 32'bx;
    endcase
end
assign Zero = (result == 0);
endmodule


module regfile(
    input  logic clk, we3,
    input  logic [4:0] a1, a2, a3,
    input  logic [31:0] wd3,
    output logic [31:0] rd1, rd2
);
logic [31:0] rf[31:0];

always_ff @(posedge clk)
    if (we3 && a3!=0) rf[a3] <= wd3;

assign rd1 = (a1!=0) ? rf[a1] : 0;
assign rd2 = (a2!=0) ? rf[a2] : 0;
endmodule


module extend(
    input  logic [31:7] instr,
    input  logic [1:0] immsrc,
    output logic [31:0] immext
);
always_comb
case(immsrc)
    2'b00: immext = {{20{instr[31]}}, instr[31:20]};
    2'b01: immext = {{20{instr[31]}}, instr[31:25], instr[11:7]};
    2'b10: immext = {{20{instr[31]}}, instr[7], instr[30:25], instr[11:8], 1'b0};
    2'b11: immext = {{12{instr[31]}}, instr[19:12], instr[20], instr[30:21], 1'b0};
    default: immext = 32'bx;
endcase
endmodule


module adder(input [31:0] a, b, output [31:0] y);
assign y = a + b;
endmodule


module flopr #(parameter WIDTH=8)(
    input  logic clk, reset,
    input  logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q
);
always_ff @(posedge clk, posedge reset)
    if (reset) q <= 0;
    else q <= d;
endmodule


module mux2 #(parameter WIDTH=8)(
    input  logic [WIDTH-1:0] d0, d1,
    input  logic s,
    output logic [WIDTH-1:0] y
);
assign y = s ? d1 : d0;
endmodule


module mux3 #(parameter WIDTH=8)(
    input  logic [WIDTH-1:0] d0, d1, d2,
    input  logic [1:0] s,
    output logic [WIDTH-1:0] y
);
assign y = s[1] ? d2 : (s[0] ? d1 : d0);
endmodule
