module tr1um_spitx (GND,
    VDD,
    busy,
    clk,
    done,
    mosi,
    sclk,
    start,
    data_in);
 inout GND;
 inout VDD;
 output busy;
 input clk;
 output done;
 output mosi;
 output sclk;
 input start;
 input [7:0] data_in;

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
 wire _064_;
 wire _065_;
 wire _066_;
 wire _067_;
 wire _068_;
 wire _069_;
 wire _070_;
 wire _071_;
 wire \bit_count[0] ;
 wire \bit_count[1] ;
 wire \bit_count[2] ;
 wire inactive_reset;
 wire phase;
 wire \shift[0] ;
 wire \shift[1] ;
 wire \shift[2] ;
 wire \shift[3] ;
 wire \shift[4] ;
 wire \shift[5] ;
 wire \shift[6] ;

 INV_X1 _072_ (.VDD(VDD),
    .GND(GND),
    .A(busy),
    .Y(_016_));
 INV_X1 _073_ (.VDD(VDD),
    .GND(GND),
    .A(_003_),
    .Y(_017_));
 INV_X1 _074_ (.VDD(VDD),
    .GND(GND),
    .A(start),
    .Y(_018_));
 NOR2 _075_ (.VDD(VDD),
    .GND(GND),
    .A(busy),
    .B(_018_),
    .Y(_019_));
 NAND2 _076_ (.VDD(VDD),
    .GND(GND),
    .A(_016_),
    .B(start),
    .Y(_020_));
 NAND3 _077_ (.VDD(VDD),
    .GND(GND),
    .A(\bit_count[0] ),
    .B(\bit_count[1] ),
    .C(\bit_count[2] ),
    .Y(_021_));
 OR2 _078_ (.VDD(VDD),
    .GND(GND),
    .A(_003_),
    .B(_021_),
    .Y(_022_));
 NAND2 _079_ (.VDD(VDD),
    .GND(GND),
    .A(busy),
    .B(_022_),
    .Y(_023_));
 NAND2 _080_ (.VDD(VDD),
    .GND(GND),
    .A(_020_),
    .B(_023_),
    .Y(_000_));
 NAND2 _081_ (.VDD(VDD),
    .GND(GND),
    .A(busy),
    .B(phase),
    .Y(_024_));
 INV_X1 _082_ (.VDD(VDD),
    .GND(GND),
    .A(_024_),
    .Y(sclk));
 NOR3 _083_ (.VDD(VDD),
    .GND(GND),
    .A(_002_),
    .B(_019_),
    .C(_022_),
    .Y(_001_));
 NOR2 _084_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[0]),
    .B(_020_),
    .Y(_025_));
 NOR2 _085_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[0] ),
    .B(_019_),
    .Y(_026_));
 NOR3 _086_ (.VDD(VDD),
    .GND(GND),
    .A(sclk),
    .B(_025_),
    .C(_026_),
    .Y(_004_));
 NAND2 _087_ (.VDD(VDD),
    .GND(GND),
    .A(_020_),
    .B(_024_),
    .Y(_027_));
 NOR2 _088_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[1]),
    .B(_020_),
    .Y(_028_));
 NOR2 _089_ (.VDD(VDD),
    .GND(GND),
    .A(_026_),
    .B(_028_),
    .Y(_029_));
 MUX2 _090_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[1] ),
    .B(_029_),
    .S(_027_),
    .Y(_005_));
 NAND2 _091_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[1] ),
    .B(_020_),
    .Y(_030_));
 NAND2 _092_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[2]),
    .B(_024_),
    .Y(_031_));
 NAND2 _093_ (.VDD(VDD),
    .GND(GND),
    .A(_030_),
    .B(_031_),
    .Y(_032_));
 MUX2 _094_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[2] ),
    .B(_032_),
    .S(_027_),
    .Y(_006_));
 NAND2 _095_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[2] ),
    .B(_020_),
    .Y(_033_));
 NAND2 _096_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[3]),
    .B(_024_),
    .Y(_034_));
 NAND2 _097_ (.VDD(VDD),
    .GND(GND),
    .A(_033_),
    .B(_034_),
    .Y(_035_));
 MUX2 _098_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[3] ),
    .B(_035_),
    .S(_027_),
    .Y(_007_));
 NAND2 _099_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[3] ),
    .B(_020_),
    .Y(_036_));
 NAND2 _100_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[4]),
    .B(_024_),
    .Y(_037_));
 NAND2 _101_ (.VDD(VDD),
    .GND(GND),
    .A(_036_),
    .B(_037_),
    .Y(_038_));
 MUX2 _102_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[4] ),
    .B(_038_),
    .S(_027_),
    .Y(_008_));
 NAND2 _103_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[4] ),
    .B(_020_),
    .Y(_039_));
 NAND2 _104_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[5]),
    .B(_024_),
    .Y(_040_));
 NAND2 _105_ (.VDD(VDD),
    .GND(GND),
    .A(_039_),
    .B(_040_),
    .Y(_041_));
 MUX2 _106_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[5] ),
    .B(_041_),
    .S(_027_),
    .Y(_009_));
 NAND2 _107_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[5] ),
    .B(_020_),
    .Y(_042_));
 NAND2 _108_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[6]),
    .B(_024_),
    .Y(_043_));
 NAND2 _109_ (.VDD(VDD),
    .GND(GND),
    .A(_042_),
    .B(_043_),
    .Y(_044_));
 MUX2 _110_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[6] ),
    .B(_044_),
    .S(_027_),
    .Y(_010_));
 NAND2 _111_ (.VDD(VDD),
    .GND(GND),
    .A(data_in[7]),
    .B(_024_),
    .Y(_045_));
 NAND2 _112_ (.VDD(VDD),
    .GND(GND),
    .A(\shift[6] ),
    .B(_020_),
    .Y(_046_));
 AND3_X1 _113_ (.VDD(VDD),
    .GND(GND),
    .A(_027_),
    .B(_045_),
    .C(_046_),
    .Y(_047_));
 NOR2 _114_ (.VDD(VDD),
    .GND(GND),
    .A(mosi),
    .B(_027_),
    .Y(_048_));
 NOR2 _115_ (.VDD(VDD),
    .GND(GND),
    .A(_047_),
    .B(_048_),
    .Y(_011_));
 AND3_X1 _116_ (.VDD(VDD),
    .GND(GND),
    .A(busy),
    .B(_017_),
    .C(_021_),
    .Y(_049_));
 OR2 _117_ (.VDD(VDD),
    .GND(GND),
    .A(_019_),
    .B(_049_),
    .Y(_050_));
 AND2_X1 _118_ (.VDD(VDD),
    .GND(GND),
    .A(\bit_count[0] ),
    .B(_050_),
    .Y(_051_));
 NOR2 _119_ (.VDD(VDD),
    .GND(GND),
    .A(\bit_count[0] ),
    .B(_049_),
    .Y(_052_));
 NOR2 _120_ (.VDD(VDD),
    .GND(GND),
    .A(_051_),
    .B(_052_),
    .Y(_012_));
 NOR2 _121_ (.VDD(VDD),
    .GND(GND),
    .A(\bit_count[1] ),
    .B(_051_),
    .Y(_053_));
 AND3_X1 _122_ (.VDD(VDD),
    .GND(GND),
    .A(\bit_count[0] ),
    .B(\bit_count[1] ),
    .C(_049_),
    .Y(_054_));
 NOR3 _123_ (.VDD(VDD),
    .GND(GND),
    .A(_019_),
    .B(_053_),
    .C(_054_),
    .Y(_013_));
 NOR2 _124_ (.VDD(VDD),
    .GND(GND),
    .A(\bit_count[2] ),
    .B(_054_),
    .Y(_055_));
 NOR2 _125_ (.VDD(VDD),
    .GND(GND),
    .A(_019_),
    .B(_055_),
    .Y(_014_));
 NAND2 _126_ (.VDD(VDD),
    .GND(GND),
    .A(_003_),
    .B(_021_),
    .Y(_056_));
 NAND2 _127_ (.VDD(VDD),
    .GND(GND),
    .A(sclk),
    .B(_056_),
    .Y(_057_));
 NAND2 _128_ (.VDD(VDD),
    .GND(GND),
    .A(phase),
    .B(_018_),
    .Y(_058_));
 NAND2 _129_ (.VDD(VDD),
    .GND(GND),
    .A(_016_),
    .B(_058_),
    .Y(_059_));
 AND2_X1 _130_ (.VDD(VDD),
    .GND(GND),
    .A(_057_),
    .B(_059_),
    .Y(_015_));
 DFFR _131_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_004_),
    .Q(\shift[0] ),
    .QB(_070_),
    .RST(inactive_reset));
 DFFR _132_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_005_),
    .Q(\shift[1] ),
    .QB(_069_),
    .RST(inactive_reset));
 DFFR _133_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_006_),
    .Q(\shift[2] ),
    .QB(_068_),
    .RST(inactive_reset));
 DFFR _134_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_007_),
    .Q(\shift[3] ),
    .QB(_067_),
    .RST(inactive_reset));
 DFFR _135_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_008_),
    .Q(\shift[4] ),
    .QB(_066_),
    .RST(inactive_reset));
 DFFR _136_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_009_),
    .Q(\shift[5] ),
    .QB(_065_),
    .RST(inactive_reset));
 DFFR _137_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_010_),
    .Q(\shift[6] ),
    .QB(_064_),
    .RST(inactive_reset));
 DFFR _138_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_011_),
    .Q(mosi),
    .QB(_063_),
    .RST(inactive_reset));
 DFFR _139_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_012_),
    .Q(\bit_count[0] ),
    .QB(_062_),
    .RST(inactive_reset));
 DFFR _140_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_013_),
    .Q(\bit_count[1] ),
    .QB(_061_),
    .RST(inactive_reset));
 DFFR _141_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_014_),
    .Q(\bit_count[2] ),
    .QB(_060_),
    .RST(inactive_reset));
 DFFR _142_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_015_),
    .Q(phase),
    .QB(_003_),
    .RST(inactive_reset));
 DFFR _143_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_001_),
    .Q(done),
    .QB(_071_),
    .RST(inactive_reset));
 DFFR _144_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_000_),
    .Q(busy),
    .QB(_002_),
    .RST(inactive_reset));
 TIELO reset_tie (.LO(inactive_reset),
    .VDD(VDD),
    .GND(GND));
endmodule
