-- Classic cottage house - Roblox setup (roblox-modeling skill)
-- Import ClassicHouse.roblox.glb with the 3D Importer, select the imported model in the Explorer, then paste this
-- into the command bar (View > Command Bar) and press Enter. It sets CollisionFidelity on every MeshPart and turns
-- collision off on decoration, then sets up level of detail. 14 MeshParts (static parts are merged per material and collision class).

local SETTINGS = { -- name = { CollisionFidelity, CanCollide }
  ["FrontDoorPanel"] = { "Box", false }, -- none
  ["BackDoor"] = { "Box", true }, -- box
  ["RoofGroupStatic1"] = { "Default", true }, -- default: GableL, GableR, Roof, RidgeCap, Chimney, ChimneyCap, ChimneyFlue, Pediment, PorchRoof, AtticFrameL, AtticFrameR, AtticGlassL, AtticGlassR, Ceiling
  ["RoofGroupStatic2"] = { "Box", false }, -- none: AtticMullVL, AtticMullVR, AtticMullHL, AtticMullHR, LampDiningCord, LampLivingCord, LampKitchenCord
  ["RoofGroupStatic3"] = { "Box", false }, -- none: LampDiningCanopy, LampLivingCanopy, LampKitchenCanopy
  ["RoofGroupStatic4"] = { "Box", false }, -- none: LampDiningShade, LampLivingShade, LampKitchenGlobe, LampBedroom
  ["ClassicHouseStatic1"] = { "Default", true }, -- default: Foundation, WallFront1, WallFront2, WallFront3, WallFront4, WallFront5, WallFront6, WallFront7, WallFront8, WallFront9, WallFront10, WallFront11, WallFront12, WallFront13, WallFront14, WallFront15, WallBack1, WallBack2, WallBack3, WallBack4, WallBack5, WallBack6, WallBack7, WallBack8, WallBack9, WallLeft1, WallLeft2, WallLeft3, WallLeft4, WallRight1, WallRight2, WallRight3, WallRight4, CornerFrontL, CornerFrontR, CornerBackL, CornerBackR, FriezeFront, FriezeBack, Stoop, Step1, Step2, ColInL, ColInR, ColOutL, ColOutR, FrontCasingL, FrontCasingR, FrontCasingHead, SidelightL, SidelightR, FrontThreshold, FrontPairFrameL, FrontPairFrameR, FrontGlass1L, FrontGlass1R, FrontGlass2L, FrontGlass2R, FrontSillL, FrontSillR, FrontHeadL, FrontHeadR, ShutterOutL, ShutterOutR, ShutterInL, ShutterInR, SideFrameL, SideFrameR, SideGlassL, SideGlassR, SideSillL, SideSillR, SideHeadL, SideHeadR, SideShutterFrontL, SideShutterFrontR, SideShutterBackL, SideShutterBackR, BackFrameL, BackFrameR, BackGlassL, BackGlassR, BackSillL, BackSillR, BackHeadL, BackHeadR, BackCasingL, BackCasingR, BackCasingHead, BackThreshold, BackStep, Floor, PartitionMid1, PartitionMid2, PartitionMid3, PartitionMid4, PartitionMid5, PartitionBack1, Hearth, FireplaceBody, Mantel, ChimneyBreast, SofaBase, ArmchairBase, CoffeeTableTop, BookcaseFireSideL, BookcaseFireSideR, BookcaseWallSideL, BookcaseWallSideR, DiningTableCloth, DiningChair1Seat, DiningChair2Seat, DiningChair3Seat, DiningChair4Seat, SideboardBody, RadioCabinet, BaseCabinets, Countertop, Range, WallCabinet, Fridge, KitchenTableCloth, KitchenChair1Seat, KitchenChair2Seat, BedBase, Headboard, Footboard, Nightstand1Body, Nightstand2Body, DresserBody, WardrobeBody
  ["ClassicHouseStatic2"] = { "Box", false }, -- none: ColBaseInL, ColBaseInR, ColCapInL, ColCapInR, ColBaseOutL, ColBaseOutR, ColCapOutL, ColCapOutR, FrontMullV1L, FrontMullV1R, FrontMullH1L, FrontMullH1R, FrontMullV2L, FrontMullV2R, FrontMullH2L, FrontMullH2R, ShutterRailOutL, ShutterRailOutR, ShutterRailInL, ShutterRailInR, SideMullVL, SideMullVR, SideMullHL, SideMullHR, BackMullVL, BackMullVR, BackMullHL, BackMullHR, DoorwayJambAL, DoorwayJambBL, DoorwayHeadL, DoorwayJambAR, DoorwayJambBR, DoorwayHeadR, Firebox, ConiferL, ConiferR, BushL, BushR, Rug, SofaLeg1, SofaLeg2, SofaLeg3, SofaLeg4, SofaBack, SofaArmL, SofaArmR, SofaCushion1, SofaCushion2, SofaCushion3, ArmchairLeg1, ArmchairLeg2, ArmchairLeg3, ArmchairLeg4, ArmchairBack, ArmchairArmL, ArmchairArmR, ArmchairCushion1, CoffeeTableLeg1, CoffeeTableLeg2, CoffeeTableLeg3, CoffeeTableLeg4, CoffeeTableShelf, CoffeeBowl, BookcaseFireBackPanel, BookcaseFireTop, BookcaseFireBottom, BookcaseFireShelf1, BookcaseFireShelf2, BookcaseFireShelf3, BookcaseFireBook0_0, BookcaseFireBook0_1, BookcaseFireBook0_2, BookcaseFireBook0_3, BookcaseFireBook0_4, BookcaseFireBook0_5, BookcaseFireBook0_6, BookcaseFireBook0_7, BookcaseFireBook0_8, BookcaseFireBook0_9, BookcaseFireBook0_10, BookcaseFireBook0_11, BookcaseFireBook0_12, BookcaseFireBook0_13, BookcaseFireBook1_0, BookcaseFireBook1_1, BookcaseFireBook1_2, BookcaseFireBook1_3, BookcaseFireBook1_4, BookcaseFireBook1_5, BookcaseFireBook1_6, BookcaseFireBook1_7, BookcaseFireBook1_8, BookcaseFireBook1_9, BookcaseFireBook1_10, BookcaseFireBook1_11, BookcaseFireBook1_12, BookcaseFireBook1_13, BookcaseFireBook2_0, BookcaseFireBook2_1, BookcaseFireBook2_2, BookcaseFireBook2_3, BookcaseFireBook2_4, BookcaseFireBook2_5, BookcaseFireBook2_6, BookcaseFireBook2_7, BookcaseFireBook2_8, BookcaseFireBook2_9, BookcaseFireBook3_0, BookcaseFireBook3_1, BookcaseFireBook3_2, BookcaseFireBook3_3, BookcaseFireBook3_4, BookcaseFireBook3_5, BookcaseFireBook3_6, BookcaseFireBook3_7, BookcaseFireBook3_8, BookcaseFireBook3_9, BookcaseFireBook3_10, BookcaseFireBook3_11, BookcaseFireBook3_12, BookcaseWallBackPanel, BookcaseWallTop, BookcaseWallBottom, BookcaseWallShelf1, BookcaseWallShelf2, BookcaseWallShelf3, BookcaseWallBook0_0, BookcaseWallBook0_1, BookcaseWallBook0_2, BookcaseWallBook0_3, BookcaseWallBook0_4, BookcaseWallBook0_5, BookcaseWallBook0_6, BookcaseWallBook0_7, BookcaseWallBook0_8, BookcaseWallBook0_9, BookcaseWallBook0_10, BookcaseWallBook0_11, BookcaseWallBook0_12, BookcaseWallBook0_13, BookcaseWallBook1_0, BookcaseWallBook1_1, BookcaseWallBook1_2, BookcaseWallBook1_3, BookcaseWallBook1_4, BookcaseWallBook1_5, BookcaseWallBook1_6, BookcaseWallBook1_7, BookcaseWallBook1_8, BookcaseWallBook1_9, BookcaseWallBook1_10, BookcaseWallBook1_11, BookcaseWallBook1_12, BookcaseWallBook2_0, BookcaseWallBook2_1, BookcaseWallBook2_2, BookcaseWallBook2_3, BookcaseWallBook2_4, BookcaseWallBook2_5, BookcaseWallBook2_6, BookcaseWallBook2_7, BookcaseWallBook2_8, BookcaseWallBook3_0, BookcaseWallBook3_1, BookcaseWallBook3_2, BookcaseWallBook3_3, BookcaseWallBook3_4, BookcaseWallBook3_5, BookcaseWallBook3_6, BookcaseWallBook3_7, BookcaseWallBook3_8, BookcaseWallBook3_9, BookcaseWallBook3_10, BookcaseWallBook3_11, BookcaseWallBook3_12, Log1, Log2, MantelClock, MantelClockFace, Candle1, Candle2, PaintingFireFrame, PaintingFireCanvas, PaintingHallFrame, PaintingHallCanvas, DiningTableLeg1, DiningTableLeg2, DiningTableLeg3, DiningTableLeg4, DiningChair1Leg1, DiningChair1Leg2, DiningChair1Leg3, DiningChair1Leg4, DiningChair1PostL, DiningChair1PostR, DiningChair1Back, DiningChair2Leg1, DiningChair2Leg2, DiningChair2Leg3, DiningChair2Leg4, DiningChair2PostL, DiningChair2PostR, DiningChair2Back, DiningChair3Leg1, DiningChair3Leg2, DiningChair3Leg3, DiningChair3Leg4, DiningChair3PostL, DiningChair3PostR, DiningChair3Back, DiningChair4Leg1, DiningChair4Leg2, DiningChair4Leg3, DiningChair4Leg4, DiningChair4PostL, DiningChair4PostR, DiningChair4Back, DiningVase, SideboardLeg1, SideboardLeg2, SideboardLeg3, SideboardLeg4, SideboardTop, SideboardDoorL, SideboardDoorM, SideboardDoorR, SideboardDrawer, SideboardVase, RadioGrille, RadioDialPanel, CurtainOuterL, CurtainInnerL, ValanceL, SideCurtainAL, SideCurtainBL, CurtainOuterR, CurtainInnerR, ValanceR, SideCurtainAR, SideCurtainBR, Linoleum, CabDoor1, CabDrawer1, CabDoor2, CabDrawer2, CabDoor3, CabDrawer3, CabDoor4, CabDrawer4, Canister1, Canister2, Canister3, RangeBackguard, RangeOvenDoor, RangeControls, Burner1, Burner2, Burner3, Burner4, WallCabDoorL, WallCabDoorR, FridgeBadge, KitchenTableLeg1, KitchenTableLeg2, KitchenTableLeg3, KitchenTableLeg4, KitchenChair1Leg1, KitchenChair1Leg2, KitchenChair1Leg3, KitchenChair1Leg4, KitchenChair1PostL, KitchenChair1PostR, KitchenChair1Back, KitchenChair2Leg1, KitchenChair2Leg2, KitchenChair2Leg3, KitchenChair2Leg4, KitchenChair2PostL, KitchenChair2PostR, KitchenChair2Back, KitchenCurtain, Carpet, BedLeg1, BedLeg2, BedLeg3, BedLeg4, Mattress, Blanket, PillowA, PillowB, Nightstand1Drawer, Nightstand2Drawer, DresserDrawer1, DresserDrawer2, DresserDrawer3, MirrorFrame, MirrorPostA, MirrorPostB, WardrobeCrown, WardrobeDoorL, WardrobeDoorR, WardrobeKnobL, WardrobeKnobR, BedCurtainA, BedCurtainB, PaintingBedFrame, PaintingBedCanvas
  ["FrontDoor"] = { "Default", true }, -- default: FrontDoor, FrontDoorGlass
  ["FrontDoorStatic1"] = { "Box", false }, -- none: FrontKnobOut, FrontKnobIn
  ["BackDoorStatic1"] = { "Box", false }, -- none: BackDoorPanelTop, BackDoorPanelBottom
  ["BackDoorStatic2"] = { "Box", false }, -- none: BackKnobOut, BackKnobIn
  ["ClassicHouseStatic3"] = { "Box", false }, -- none: FloorLampBase, FloorLampPole, Candle1Holder, Candle2Holder, SideboardLampBase, SideboardLampStem, CabHandle1, CabHandle2, CabHandle3, CabHandle4, SinkRim, SinkBasin, FaucetStem, FaucetSpout, RangeOvenHandle, Kettle, FridgeHandle, BedLamp1Base, BedLamp1Stem, BedLamp2Base, BedLamp2Stem, MirrorGlass
  ["ClassicHouseStatic4"] = { "Box", false }, -- none: FloorLampShade, SideboardLampShade, BedLamp1Shade, BedLamp2Shade
}
local root = game:GetService("Selection"):Get()[1]
assert(root, "select the imported ClassicHouse model in the Explorer first")
local done = 0
for _, d in ipairs(root:GetDescendants()) do
  local s = d:IsA("MeshPart") and SETTINGS[d.Name]
  if s then
    d.CollisionFidelity = Enum.CollisionFidelity[s[1]]
    d.CanCollide = s[2]
    if not s[2] then d.CanTouch = false end
    done += 1
  end
end
print(("[rmodel] collision set on %d of 14 MeshParts"):format(done))

-- Level of detail (the roblox-performance skill's LodController): near, the full model in "Detail" shows; far, it is
-- removed and the one-mesh stand-in "Simple" shows instead (about half the triangles, 1 draw call).
local simple = root:FindFirstChild("Simple", true)
if simple and simple:IsA("MeshPart") then
  local holder = simple.Parent :: Instance
  local detail = holder:FindFirstChild("Detail") or Instance.new("Model")
  detail.Name = "Detail"
  for _, c in ipairs(holder:GetChildren()) do
    if c ~= simple and c ~= detail then c.Parent = detail end
  end
  detail.Parent = holder
  simple.CanCollide = false
  simple.CanTouch = false
  simple.CanQuery = false
  simple.CastShadow = false
  game:GetService("CollectionService"):AddTag(holder, "PerfLod")
  print("[rmodel] LOD set up on " .. holder:GetFullName() .. ": Detail near, Simple far (tag PerfLod)")
else
  warn("[rmodel] no Simple stand-in found: import ClassicHouse.roblox.glb (not ClassicHouse.glb)")
end
