module tr1um_uarttx_big (GND,
    VDD,
    clk,
    tx);
 inout GND;
 inout VDD;
 input clk;
 output tx;

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
 wire _072_;
 wire _073_;
 wire _074_;
 wire _075_;
 wire _076_;
 wire _077_;
 wire _078_;
 wire _079_;
 wire _080_;
 wire _081_;
 wire _082_;
 wire _083_;
 wire _084_;
 wire _085_;
 wire _086_;
 wire _087_;
 wire _088_;
 wire _089_;
 wire _090_;
 wire _091_;
 wire _092_;
 wire _093_;
 wire _094_;
 wire _095_;
 wire _096_;
 wire _097_;
 wire _098_;
 wire _099_;
 wire _100_;
 wire _101_;
 wire _102_;
 wire _103_;
 wire _104_;
 wire _105_;
 wire _106_;
 wire _107_;
 wire _108_;
 wire _109_;
 wire inactive_reset;
 wire \phase[0] ;
 wire \phase[10] ;
 wire \phase[11] ;
 wire \phase[12] ;
 wire \phase[13] ;
 wire \phase[14] ;
 wire \phase[15] ;
 wire \phase[1] ;
 wire \phase[2] ;
 wire \phase[3] ;
 wire \phase[4] ;
 wire \phase[5] ;
 wire \phase[6] ;
 wire \phase[7] ;
 wire \phase[8] ;
 wire \phase[9] ;

 INV_X1 _110_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[7] ),
    .Y(_048_));
 INV_X1 _111_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[8] ),
    .Y(_049_));
 INV_X1 _112_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[9] ),
    .Y(_050_));
 INV_X1 _113_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[11] ),
    .Y(_051_));
 INV_X1 _114_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[12] ),
    .Y(_052_));
 INV_X1 _115_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .Y(_053_));
 INV_X1 _116_ (.VDD(VDD),
    .GND(GND),
    .A(_000_),
    .Y(_054_));
 NAND2 _117_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[1] ),
    .B(\phase[0] ),
    .Y(_055_));
 XOR2 _118_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[1] ),
    .B(\phase[0] ),
    .Y(_009_));
 NAND3 _119_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[1] ),
    .B(\phase[0] ),
    .C(\phase[2] ),
    .Y(_056_));
 XNOR2 _120_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[2] ),
    .B(_055_),
    .Y(_010_));
 AND4_X1 _121_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[1] ),
    .B(\phase[0] ),
    .C(\phase[2] ),
    .D(\phase[3] ),
    .Y(_057_));
 XNOR2 _122_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[3] ),
    .B(_056_),
    .Y(_011_));
 NAND2 _123_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[4] ),
    .B(_057_),
    .Y(_058_));
 XOR2 _124_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[4] ),
    .B(_057_),
    .Y(_012_));
 NAND3 _125_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[4] ),
    .B(\phase[5] ),
    .C(_057_),
    .Y(_059_));
 XNOR2 _126_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[5] ),
    .B(_058_),
    .Y(_013_));
 NAND4 _127_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[4] ),
    .B(\phase[5] ),
    .C(\phase[6] ),
    .D(_057_),
    .Y(_060_));
 XNOR2 _128_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[6] ),
    .B(_059_),
    .Y(_014_));
 NOR2 _129_ (.VDD(VDD),
    .GND(GND),
    .A(_048_),
    .B(_060_),
    .Y(_061_));
 XNOR2 _130_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[7] ),
    .B(_060_),
    .Y(_015_));
 NOR3 _131_ (.VDD(VDD),
    .GND(GND),
    .A(_048_),
    .B(_049_),
    .C(_060_),
    .Y(_062_));
 XNOR2 _132_ (.VDD(VDD),
    .GND(GND),
    .A(_049_),
    .B(_061_),
    .Y(_016_));
 NAND3 _133_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[7] ),
    .B(\phase[8] ),
    .C(\phase[9] ),
    .Y(_063_));
 NOR2 _134_ (.VDD(VDD),
    .GND(GND),
    .A(_060_),
    .B(_063_),
    .Y(_064_));
 XNOR2 _135_ (.VDD(VDD),
    .GND(GND),
    .A(_050_),
    .B(_062_),
    .Y(_017_));
 NAND2 _136_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[10] ),
    .B(_064_),
    .Y(_065_));
 XOR2 _137_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[10] ),
    .B(_064_),
    .Y(_003_));
 NAND3 _138_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[10] ),
    .B(\phase[11] ),
    .C(_064_),
    .Y(_066_));
 XNOR2 _139_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[11] ),
    .B(_065_),
    .Y(_004_));
 NAND2 _140_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[11] ),
    .B(\phase[12] ),
    .Y(_067_));
 NOR2 _141_ (.VDD(VDD),
    .GND(GND),
    .A(_065_),
    .B(_067_),
    .Y(_068_));
 XNOR2 _142_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[12] ),
    .B(_066_),
    .Y(_005_));
 NOR2 _143_ (.VDD(VDD),
    .GND(GND),
    .A(_052_),
    .B(\phase[13] ),
    .Y(_069_));
 NAND2 _144_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_068_),
    .Y(_070_));
 XOR2 _145_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_068_),
    .Y(_006_));
 XNOR2 _146_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[11] ),
    .B(\phase[12] ),
    .Y(_071_));
 XOR2 _147_ (.VDD(VDD),
    .GND(GND),
    .A(_001_),
    .B(_070_),
    .Y(_007_));
 NAND3 _148_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(\phase[14] ),
    .C(_068_),
    .Y(_072_));
 XNOR2 _149_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[15] ),
    .B(_072_),
    .Y(_008_));
 NAND2 _150_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .B(_067_),
    .Y(_073_));
 NOR2 _151_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[9] ),
    .B(\phase[10] ),
    .Y(_074_));
 NAND4 _152_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[7] ),
    .B(\phase[8] ),
    .C(_073_),
    .D(_074_),
    .Y(_075_));
 NOR2 _153_ (.VDD(VDD),
    .GND(GND),
    .A(_051_),
    .B(\phase[12] ),
    .Y(_076_));
 NOR2 _154_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[11] ),
    .B(_052_),
    .Y(_077_));
 NAND2 _155_ (.VDD(VDD),
    .GND(GND),
    .A(_051_),
    .B(\phase[12] ),
    .Y(_078_));
 AND2_X1 _156_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_078_),
    .Y(_079_));
 AND2_X1 _157_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_071_),
    .Y(_080_));
 NOR2 _158_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_077_),
    .Y(_081_));
 NOR2 _159_ (.VDD(VDD),
    .GND(GND),
    .A(_080_),
    .B(_081_),
    .Y(_082_));
 NOR2 _160_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .B(_082_),
    .Y(_083_));
 NOR2 _161_ (.VDD(VDD),
    .GND(GND),
    .A(_075_),
    .B(_083_),
    .Y(_084_));
 NAND2 _162_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[7] ),
    .B(_049_),
    .Y(_085_));
 OR3 _163_ (.VDD(VDD),
    .GND(GND),
    .A(_050_),
    .B(\phase[10] ),
    .C(_085_),
    .Y(_086_));
 NOR3 _164_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .B(_069_),
    .C(_079_),
    .Y(_087_));
 NOR3 _165_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_053_),
    .C(_078_),
    .Y(_088_));
 NOR2 _166_ (.VDD(VDD),
    .GND(GND),
    .A(_087_),
    .B(_088_),
    .Y(_089_));
 NOR2 _167_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_067_),
    .Y(_090_));
 NOR2 _168_ (.VDD(VDD),
    .GND(GND),
    .A(_086_),
    .B(_089_),
    .Y(_091_));
 NOR3 _169_ (.VDD(VDD),
    .GND(GND),
    .A(_051_),
    .B(\phase[12] ),
    .C(\phase[13] ),
    .Y(_092_));
 NOR3 _170_ (.VDD(VDD),
    .GND(GND),
    .A(_053_),
    .B(_080_),
    .C(_092_),
    .Y(_093_));
 AND3_X1 _171_ (.VDD(VDD),
    .GND(GND),
    .A(_051_),
    .B(\phase[12] ),
    .C(\phase[13] ),
    .Y(_094_));
 NOR3 _172_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .B(_090_),
    .C(_094_),
    .Y(_095_));
 NOR2 _173_ (.VDD(VDD),
    .GND(GND),
    .A(_093_),
    .B(_095_),
    .Y(_096_));
 NOR2 _174_ (.VDD(VDD),
    .GND(GND),
    .A(_085_),
    .B(_096_),
    .Y(_018_));
 NOR2 _175_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_071_),
    .Y(_019_));
 NAND2 _176_ (.VDD(VDD),
    .GND(GND),
    .A(_048_),
    .B(\phase[8] ),
    .Y(_020_));
 NOR2 _177_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .B(_078_),
    .Y(_021_));
 NOR4 _178_ (.VDD(VDD),
    .GND(GND),
    .A(_080_),
    .B(_019_),
    .C(_020_),
    .D(_021_),
    .Y(_022_));
 NOR2 _179_ (.VDD(VDD),
    .GND(GND),
    .A(_018_),
    .B(_022_),
    .Y(_023_));
 NOR3 _180_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[9] ),
    .B(\phase[10] ),
    .C(_023_),
    .Y(_024_));
 NOR3 _181_ (.VDD(VDD),
    .GND(GND),
    .A(_084_),
    .B(_091_),
    .C(_024_),
    .Y(_025_));
 NOR2 _182_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[15] ),
    .B(_025_),
    .Y(_026_));
 NAND2 _183_ (.VDD(VDD),
    .GND(GND),
    .A(_053_),
    .B(\phase[15] ),
    .Y(_027_));
 OR3 _184_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_077_),
    .C(_086_),
    .Y(_028_));
 NOR2 _185_ (.VDD(VDD),
    .GND(GND),
    .A(_069_),
    .B(_075_),
    .Y(_029_));
 NAND2 _186_ (.VDD(VDD),
    .GND(GND),
    .A(_071_),
    .B(_029_),
    .Y(_030_));
 NOR2 _187_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[13] ),
    .B(_054_),
    .Y(_031_));
 NOR3 _188_ (.VDD(VDD),
    .GND(GND),
    .A(_094_),
    .B(_020_),
    .C(_031_),
    .Y(_032_));
 NOR3 _189_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[11] ),
    .B(_069_),
    .C(_085_),
    .Y(_033_));
 OR2 _190_ (.VDD(VDD),
    .GND(GND),
    .A(_032_),
    .B(_033_),
    .Y(_034_));
 NAND2 _191_ (.VDD(VDD),
    .GND(GND),
    .A(_074_),
    .B(_034_),
    .Y(_035_));
 AND3_X1 _192_ (.VDD(VDD),
    .GND(GND),
    .A(_028_),
    .B(_030_),
    .C(_035_),
    .Y(_036_));
 NOR2 _193_ (.VDD(VDD),
    .GND(GND),
    .A(_027_),
    .B(_036_),
    .Y(_037_));
 NOR3 _194_ (.VDD(VDD),
    .GND(GND),
    .A(_002_),
    .B(_076_),
    .C(_027_),
    .Y(_038_));
 NOR3 _195_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[14] ),
    .B(_079_),
    .C(_019_),
    .Y(_039_));
 NOR2 _196_ (.VDD(VDD),
    .GND(GND),
    .A(_053_),
    .B(_077_),
    .Y(_040_));
 NOR3 _197_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[15] ),
    .B(_039_),
    .C(_040_),
    .Y(_041_));
 NOR2 _198_ (.VDD(VDD),
    .GND(GND),
    .A(_038_),
    .B(_041_),
    .Y(_042_));
 NAND2 _199_ (.VDD(VDD),
    .GND(GND),
    .A(_048_),
    .B(_049_),
    .Y(_043_));
 NOR4 _200_ (.VDD(VDD),
    .GND(GND),
    .A(_050_),
    .B(\phase[10] ),
    .C(_042_),
    .D(_043_),
    .Y(_044_));
 NAND3 _201_ (.VDD(VDD),
    .GND(GND),
    .A(_048_),
    .B(_049_),
    .C(_050_),
    .Y(_045_));
 NAND2 _202_ (.VDD(VDD),
    .GND(GND),
    .A(\phase[10] ),
    .B(_045_),
    .Y(_046_));
 NAND2 _203_ (.VDD(VDD),
    .GND(GND),
    .A(_063_),
    .B(_046_),
    .Y(_047_));
 OR4 _204_ (.VDD(VDD),
    .GND(GND),
    .A(_026_),
    .B(_037_),
    .C(_044_),
    .D(_047_),
    .Y(tx));
 DFFR _205_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_097_),
    .Q(\phase[0] ),
    .QB(_097_),
    .RST(inactive_reset));
 DFFR _206_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_009_),
    .Q(\phase[1] ),
    .QB(_099_),
    .RST(inactive_reset));
 DFFR _207_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_010_),
    .Q(\phase[2] ),
    .QB(_100_),
    .RST(inactive_reset));
 DFFR _208_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_011_),
    .Q(\phase[3] ),
    .QB(_101_),
    .RST(inactive_reset));
 DFFR _209_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_012_),
    .Q(\phase[4] ),
    .QB(_102_),
    .RST(inactive_reset));
 DFFR _210_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_013_),
    .Q(\phase[5] ),
    .QB(_103_),
    .RST(inactive_reset));
 DFFR _211_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_014_),
    .Q(\phase[6] ),
    .QB(_104_),
    .RST(inactive_reset));
 DFFR _212_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_015_),
    .Q(\phase[7] ),
    .QB(_105_),
    .RST(inactive_reset));
 DFFR _213_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_016_),
    .Q(\phase[8] ),
    .QB(_106_),
    .RST(inactive_reset));
 DFFR _214_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_017_),
    .Q(\phase[9] ),
    .QB(_107_),
    .RST(inactive_reset));
 DFFR _215_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_003_),
    .Q(\phase[10] ),
    .QB(_108_),
    .RST(inactive_reset));
 DFFR _216_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_004_),
    .Q(\phase[11] ),
    .QB(_000_),
    .RST(inactive_reset));
 DFFR _217_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_005_),
    .Q(\phase[12] ),
    .QB(_109_),
    .RST(inactive_reset));
 DFFR _218_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_006_),
    .Q(\phase[13] ),
    .QB(_002_),
    .RST(inactive_reset));
 DFFR _219_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_007_),
    .Q(\phase[14] ),
    .QB(_001_),
    .RST(inactive_reset));
 DFFR _220_ (.VDD(VDD),
    .GND(GND),
    .CK(clk),
    .D(_008_),
    .Q(\phase[15] ),
    .QB(_098_),
    .RST(inactive_reset));
 TIELO reset_tie (.LO(inactive_reset),
    .VDD(VDD),
    .GND(GND));
endmodule
