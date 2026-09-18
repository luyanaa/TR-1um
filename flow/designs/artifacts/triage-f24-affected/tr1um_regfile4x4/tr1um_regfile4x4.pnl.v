module tr1um_regfile4x4 (GND,
    VDD,
    clk,
    write_enable,
    read_addr,
    read_data,
    write_addr,
    write_data);
 inout GND;
 inout VDD;
 input clk;
 input write_enable;
 input [1:0] read_addr;
 output [3:0] read_data;
 input [1:0] write_addr;
 input [3:0] write_data;

 wire _000_;
 wire _001_;
 wire _002_;
 wire _003_;
 wire _004_;
 wire _005_;
 wire _006_;
 wire _007_;
 wire _008_;
 wire _009_;
 wire _010_;
 wire _011_;
 wire _012_;
 wire _013_;
 wire _014_;
 wire _015_;
 wire _016_;
 wire _017_;
 wire _018_;
 wire _019_;
 wire _020_;
 wire _021_;
 wire _022_;
 wire _023_;
 wire _024_;
 wire _025_;
 wire _026_;
 wire _027_;
 wire _028_;
 wire _029_;
 wire _030_;
 wire _031_;
 wire _032_;
 wire _033_;
 wire _034_;
 wire _035_;
 wire _036_;
 wire _037_;
 wire _038_;
 wire _039_;
 wire _040_;
 wire _041_;
 wire _042_;
 wire _043_;
 wire _044_;
 wire _045_;
 wire _046_;
 wire _047_;
 wire _048_;
 wire _049_;
 wire _050_;
 wire _051_;
 wire _052_;
 wire _053_;
 wire _054_;
 wire _055_;
 wire _056_;
 wire _057_;
 wire _058_;
 wire _059_;
 wire _060_;
 wire _061_;
 wire _062_;
 wire _063_;
 wire inactive_reset;
 wire \memory[0][0] ;
 wire \memory[0][1] ;
 wire \memory[0][2] ;
 wire \memory[0][3] ;
 wire \memory[1][0] ;
 wire \memory[1][1] ;
 wire \memory[1][2] ;
 wire \memory[1][3] ;
 wire \memory[2][0] ;
 wire \memory[2][1] ;
 wire \memory[2][2] ;
 wire \memory[2][3] ;
 wire \memory[3][0] ;
 wire \memory[3][1] ;
 wire \memory[3][2] ;
 wire \memory[3][3] ;

 INV_X1 _064_ (.VDD(VDD),
    .GND(GND),
    .A(write_enable),
    .Y(_016_));
 INV_X1 _065_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[0]),
    .Y(_017_));
 INV_X1 _066_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[1]),
    .Y(_018_));
 NAND2 _067_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(_018_),
    .Y(_019_));
 OR2 _068_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][0] ),
    .B(_019_),
    .Y(_020_));
 NOR2 _069_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(\memory[1][0] ),
    .Y(_021_));
 OR2 _070_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[1]),
    .B(_021_),
    .Y(_022_));
 NAND3 _071_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[0]),
    .B(read_addr[1]),
    .C(\memory[3][0] ),
    .Y(_023_));
 NAND2 _072_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(\memory[2][0] ),
    .Y(_024_));
 NAND3 _073_ (.VDD(VDD),
    .GND(GND),
    .A(_022_),
    .B(_023_),
    .C(_024_),
    .Y(_025_));
 AND2_X1 _074_ (.VDD(VDD),
    .GND(GND),
    .A(_020_),
    .B(_025_),
    .Y(read_data[0]));
 NOR2 _075_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][1] ),
    .B(_019_),
    .Y(_026_));
 NAND3 _076_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[0]),
    .B(read_addr[1]),
    .C(\memory[3][1] ),
    .Y(_027_));
 NOR2 _077_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(read_addr[1]),
    .Y(_028_));
 NAND2 _078_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[1][1] ),
    .B(_028_),
    .Y(_029_));
 NAND2 _079_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(\memory[2][1] ),
    .Y(_030_));
 AND4_X1 _080_ (.VDD(VDD),
    .GND(GND),
    .A(_019_),
    .B(_027_),
    .C(_029_),
    .D(_030_),
    .Y(_031_));
 NOR2 _081_ (.VDD(VDD),
    .GND(GND),
    .A(_026_),
    .B(_031_),
    .Y(read_data[1]));
 NOR2 _082_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][2] ),
    .B(_019_),
    .Y(_032_));
 NAND3 _083_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[0]),
    .B(read_addr[1]),
    .C(\memory[3][2] ),
    .Y(_033_));
 NAND2 _084_ (.VDD(VDD),
    .GND(GND),
    .A(_018_),
    .B(\memory[1][2] ),
    .Y(_034_));
 NAND2 _085_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(\memory[2][2] ),
    .Y(_035_));
 AND4_X1 _086_ (.VDD(VDD),
    .GND(GND),
    .A(_019_),
    .B(_033_),
    .C(_034_),
    .D(_035_),
    .Y(_036_));
 NOR2 _087_ (.VDD(VDD),
    .GND(GND),
    .A(_032_),
    .B(_036_),
    .Y(read_data[2]));
 NOR2 _088_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][3] ),
    .B(_019_),
    .Y(_037_));
 NAND2 _089_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[1][3] ),
    .B(_028_),
    .Y(_038_));
 NAND3 _090_ (.VDD(VDD),
    .GND(GND),
    .A(read_addr[0]),
    .B(read_addr[1]),
    .C(\memory[3][3] ),
    .Y(_039_));
 NAND2 _091_ (.VDD(VDD),
    .GND(GND),
    .A(_017_),
    .B(\memory[2][3] ),
    .Y(_040_));
 AND4_X1 _092_ (.VDD(VDD),
    .GND(GND),
    .A(_019_),
    .B(_038_),
    .C(_039_),
    .D(_040_),
    .Y(_041_));
 NOR2 _093_ (.VDD(VDD),
    .GND(GND),
    .A(_037_),
    .B(_041_),
    .Y(read_data[3]));
 NOR2 _094_ (.VDD(VDD),
    .GND(GND),
    .A(write_addr[0]),
    .B(_016_),
    .Y(_042_));
 NOR3 _095_ (.VDD(VDD),
    .GND(GND),
    .A(write_addr[1]),
    .B(write_addr[0]),
    .C(_016_),
    .Y(_043_));
 MUX2 _096_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][0] ),
    .B(write_data[0]),
    .S(_043_),
    .Y(_000_));
 MUX2 _097_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][1] ),
    .B(write_data[1]),
    .S(_043_),
    .Y(_001_));
 MUX2 _098_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][2] ),
    .B(write_data[2]),
    .S(_043_),
    .Y(_002_));
 MUX2 _099_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[0][3] ),
    .B(write_data[3]),
    .S(_043_),
    .Y(_003_));
 NAND2 _100_ (.VDD(VDD),
    .GND(GND),
    .A(write_addr[0]),
    .B(write_enable),
    .Y(_044_));
 NOR2 _101_ (.VDD(VDD),
    .GND(GND),
    .A(write_addr[1]),
    .B(_044_),
    .Y(_045_));
 MUX2 _102_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[1][0] ),
    .B(write_data[0]),
    .S(_045_),
    .Y(_004_));
 MUX2 _103_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[1][1] ),
    .B(write_data[1]),
    .S(_045_),
    .Y(_005_));
 MUX2 _104_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[1][2] ),
    .B(write_data[2]),
    .S(_045_),
    .Y(_006_));
 MUX2 _105_ (.VDD(VDD),
    .GND(GND),
    .A(\memory[1][3] ),
    .B(write_data[3]),
    .S(_045_),
    .Y(_007_));
 NAND2 _106_ (.VDD(VDD),
    .GND(GND),
    .A(write_addr[1]),
    .B(_042_),
    .Y(_046_));
 MUX2 _107_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[0]),
    .B(\memory[2][0] ),
    .S(_046_),
    .Y(_008_));
 MUX2 _108_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[1]),
    .B(\memory[2][1] ),
    .S(_046_),
    .Y(_009_));
 MUX2 _109_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[2]),
    .B(\memory[2][2] ),
    .S(_046_),
    .Y(_010_));
 MUX2 _110_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[3]),
    .B(\memory[2][3] ),
    .S(_046_),
    .Y(_011_));
 NAND3 _111_ (.VDD(VDD),
    .GND(GND),
    .A(write_addr[1]),
    .B(write_addr[0]),
    .C(write_enable),
    .Y(_047_));
 MUX2 _112_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[0]),
    .B(\memory[3][0] ),
    .S(_047_),
    .Y(_012_));
 MUX2 _113_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[1]),
    .B(\memory[3][1] ),
    .S(_047_),
    .Y(_013_));
 MUX2 _114_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[2]),
    .B(\memory[3][2] ),
    .S(_047_),
    .Y(_014_));
 MUX2 _115_ (.VDD(VDD),
    .GND(GND),
    .A(write_data[3]),
    .B(\memory[3][3] ),
    .S(_047_),
    .Y(_015_));
 DFFR _116_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_000_),
    .Q(\memory[0][0] ),
    .QB(_063_),
    .RST(inactive_reset));
 DFFR _117_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_001_),
    .Q(\memory[0][1] ),
    .QB(_062_),
    .RST(inactive_reset));
 DFFR _118_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_002_),
    .Q(\memory[0][2] ),
    .QB(_061_),
    .RST(inactive_reset));
 DFFR _119_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_003_),
    .Q(\memory[0][3] ),
    .QB(_060_),
    .RST(inactive_reset));
 DFFR _120_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_004_),
    .Q(\memory[1][0] ),
    .QB(_059_),
    .RST(inactive_reset));
 DFFR _121_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_005_),
    .Q(\memory[1][1] ),
    .QB(_058_),
    .RST(inactive_reset));
 DFFR _122_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_006_),
    .Q(\memory[1][2] ),
    .QB(_057_),
    .RST(inactive_reset));
 DFFR _123_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_007_),
    .Q(\memory[1][3] ),
    .QB(_056_),
    .RST(inactive_reset));
 DFFR _124_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_008_),
    .Q(\memory[2][0] ),
    .QB(_055_),
    .RST(inactive_reset));
 DFFR _125_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_009_),
    .Q(\memory[2][1] ),
    .QB(_054_),
    .RST(inactive_reset));
 DFFR _126_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_010_),
    .Q(\memory[2][2] ),
    .QB(_053_),
    .RST(inactive_reset));
 DFFR _127_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_011_),
    .Q(\memory[2][3] ),
    .QB(_052_),
    .RST(inactive_reset));
 DFFR _128_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_012_),
    .Q(\memory[3][0] ),
    .QB(_051_),
    .RST(inactive_reset));
 DFFR _129_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_013_),
    .Q(\memory[3][1] ),
    .QB(_050_),
    .RST(inactive_reset));
 DFFR _130_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_014_),
    .Q(\memory[3][2] ),
    .QB(_049_),
    .RST(inactive_reset));
 DFFR _131_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_015_),
    .Q(\memory[3][3] ),
    .QB(_048_),
    .RST(inactive_reset));
 TIELO reset_tie (.LO(inactive_reset),
    .VDD(VDD),
    .GND(GND));
endmodule
