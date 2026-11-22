-- DogAnimator end-to-end test against Blender. Run through tests/run_animator_test.py, which bundles this file with
-- mock_roblox.luau, roblox/DogAnimator.luau, roblox/DogAnimations.luau and out/dog_fixture.luau (Blender's
-- evaluated bone poses), since the luau CLI has no file access and its modules don't share globals.
--
-- The fake import is deliberately awkward: Blender's axes converted to Roblox's (x, z, -y) and then yawed 37°,
-- scaled 1.3x, offset, and every bone given a random local axis convention. The animator must still reproduce
-- Blender's pose: same bone positions and orientations, frame by frame, for every clip.

local DogAnimator, DogAnimations, Fixture = ...

local failures = 0
local function check(ok, msg)
	if not ok then
		failures += 1
		print("FAIL " .. msg)
	end
end

-- the fake import -----------------------------------------------------------------------------------------------
local yaw = math.rad(37)
local axes = CFrame.fromMatrix(Vector3.zero, Vector3.new(1, 0, 0), Vector3.new(0, 0, -1), Vector3.new(0, 1, 0))
-- columns: Blender X -> Roblox X, Blender Y -> Roblox -Z, Blender Z -> Roblox Y
local yawCF = CFrame.fromMatrix(Vector3.zero, Vector3.new(math.cos(yaw), 0, -math.sin(yaw)), Vector3.new(0, 1, 0),
	Vector3.new(math.sin(yaw), 0, math.cos(yaw)))
local IMP = yawCF * axes
local IMP_POS = Vector3.new(10, 5, -3)
local S = DogAnimations.studsPerMetre * 1.3

local seed = 12345
local function rnd()
	seed = (seed * 1103515245 + 12345) % 2147483648
	return seed / 2147483648 * 2 - 1
end

local function v(t)
	return Vector3.new(t[1], t[2], t[3])
end
local function q(t)
	return CFrame.new(0, 0, 0, t[1], t[2], t[3], t[4])
end

local part = { Name = "Dog", ClassName = "MeshPart" }
function part:IsA(c)
	return c == "MeshPart" or c == "BasePart"
end

local bones, byName, conv, restWorld = {}, {}, {}, {}
for _, name in DogAnimations.order do
	local r = Fixture.rest[name]
	conv[name] = CFrame.new(0, 0, 0, rnd(), rnd(), rnd(), rnd())
	restWorld[name] = CFrame.new(IMP_POS + IMP:VectorToWorldSpace(v(r.head) * S)) * IMP * q(r.rot) * conv[name]
	local parentName = DogAnimations.parents[name]
	local b = { Name = name, ClassName = "Bone", Transform = CFrame.identity }
	function b:IsA(c)
		return c == "Bone"
	end
	b.Parent = parentName and byName[parentName] or part
	b.CFrame = parentName and restWorld[parentName]:Inverse() * restWorld[name] or restWorld[name]
	byName[name] = b
	table.insert(bones, b)
end

local anim = DogAnimator.fromBones(bones, DogAnimations)
check(anim.fitError < 1e-3, ("axis fit error %.5f m"):format(anim.fitError))
check(math.abs(anim.scale - 1.3) < 1e-3, ("scale %.4f, expected 1.3"):format(anim.scale))

local function worldOf()
	local w = {}
	for _, name in DogAnimations.order do
		local b = byName[name]
		local parentWorld = b.Parent.ClassName == "Bone" and w[b.Parent.Name] or CFrame.identity
		w[name] = parentWorld * b.CFrame * b.Transform
	end
	return w
end

local function rotDiff(a, b)
	local m = 0
	for i = 1, 9 do
		m = math.max(m, math.abs(a.r[i] - b.r[i]))
	end
	return m
end

-- 1. every fixture frame of every clip matches Blender ------------------------------------------------------------
local worstPos, worstRot, compared = 0, 0, 0
for clipName, frames in Fixture.clips do
	local clip = DogAnimations.clips[clipName]
	for frame, pose in frames do
		anim:Pose(clipName, frame)
		local w = worldOf()
		local expect = {}
		for name, p in pose do
			expect[name] = CFrame.new(IMP_POS + IMP:VectorToWorldSpace(v(p.head) * S)) * IMP * q(p.rot) * conv[name]
		end
		-- the Jump clip's upward root lift is left to the Humanoid: compare positions relative to DogRoot there
		local rel = clip.physicsLift
		for name, e in expect do
			local got = w[name]
			local dp
			if rel then
				dp = ((got.Position - w.DogRoot.Position) - (e.Position - expect.DogRoot.Position)).Magnitude
			else
				dp = (got.Position - e.Position).Magnitude
			end
			local dr = rotDiff(got, e)
			worstPos = math.max(worstPos, dp / S)
			worstRot = math.max(worstRot, dr)
			compared += 1
			check(dp / S < 0.002, ("%s frame %d %s: position off by %.4f m"):format(clipName, frame, name, dp / S))
			check(dr < 0.004, ("%s frame %d %s: orientation off by %.4f"):format(clipName, frame, name, dr))
		end
	end
end
print(("pose match: %d bone poses, worst position %.5f m, worst rotation-matrix entry %.5f"):format(compared,
	worstPos, worstRot))

-- 2. state machine: idle -> walk -> run -> crouch/jump/air/land -> walk -> idle, no NaNs, right clips ----------------
anim.tracks = {}
anim.mode = "ground"
anim.locoName = nil
local seen, modes = {}, {}
local dt = 1 / 60
local t = 0
local jumped, landed = false, false
while t < 7 do
	local speed = (t < 1 and 0) or (t < 2.5 and 5 * 1.3) or (t < 4 and 15 * 1.3) or (t < 5.5 and 5 * 1.3) or 0
	if t >= 3.0 and not jumped then
		jumped = true
		anim:Crouch()
	end
	if t >= 3.22 and anim.mode == "crouch" then
		anim:Jump()
		anim:Fall() -- the Humanoid goes Jumping -> Freefall at once; Fall must not cut the takeoff
	end
	if t >= 3.6 and not landed and (anim.mode == "air" or anim.mode == "jump") then
		landed = true
		anim:Land()
	end
	anim:SetLocomotion(speed)
	anim:Step(dt)
	modes[anim.mode] = true
	if anim.mode == "ground" and anim.locoName then
		seen[anim.locoName .. "@" .. tostring(speed)] = true
	end
	for _, b in bones do
		local p = b.Transform.Position
		for i = 1, 9 do
			if b.Transform.r[i] ~= b.Transform.r[i] then
				check(false, "NaN in " .. b.Name .. " at t=" .. t)
				break
			end
		end
		check(p.X == p.X and p.Y == p.Y and p.Z == p.Z, "NaN position in " .. b.Name)
	end
	t += dt
end
check(seen["Idle@0"], "idle when standing")
check(seen["Walk@" .. tostring(5 * 1.3)], "walk at 5 studs/s (x1.3 scale)")
check(seen["Run@" .. tostring(15 * 1.3)], "run at 15 studs/s (x1.3 scale)")
check(modes.crouch and modes.jump and modes.air and modes.land, "went through crouch, jump, air and land")
check(anim.mode == "ground", "back on the ground at the end, mode = " .. anim.mode)

-- 3. Destroy puts the rest pose back ---------------------------------------------------------------------------
anim:Destroy()
local w = worldOf()
local restErr = 0
for name, rw in restWorld do
	restErr = math.max(restErr, (w[name].Position - rw.Position).Magnitude)
end
check(restErr < 1e-6, "Destroy restores the rest pose")

if failures > 0 then
	print(("%d check(s) failed"):format(failures))
	error("animator test failed")
end
print("animator test passed")
