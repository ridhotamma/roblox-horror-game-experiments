--!nonstrict
-- DogAnimator: plays the Dog's baked clips (DogAnimations) on the imported skinned mesh by writing Bone.Transform.
-- No animation upload, no Animator/KeyframeSequence: the clips ship as data and run anywhere the model goes.
--
-- Why it is robust to the import: every frame of a clip stores, per bone, a rotation delta in Blender's model axes
-- (how far the bone has turned from its rest orientation) plus the DogRoot offset. At start the animator reads the
-- imported rest skeleton (Bone.CFrame chain) and fits Blender's axes onto it from three bones (DogRoot, Hips, Head):
-- so it does not matter how the 3D Importer rotated, scaled or offset the model, or which local axes it gave each
-- bone. Positions are never taken from the data except the root offset; children ride on their parents.
--
-- Bone.Transform does not replicate: run this on every client (DogController is a Script with RunContext Client).
--
-- API
--   local anim = DogAnimator.new(model, DogAnimations)
--   anim:SetLocomotion(speedStudsPerSecond)   -- picks Idle / Walk / Run and the playback rate (call every frame)
--   anim:Crouch()                             -- jump anticipation (frames 0-9); hold until Jump()
--   anim:Jump()                               -- push off and the airborne poses; holds the last air pose
--   anim:Land()                               -- landing, then back to locomotion
--   anim:PlayIdleVariant(name?)               -- play an idle variant now (random one if name is nil)
--   anim:SetIdleVariantDelay(min, max)        -- seconds of plain Idle between variants (default 6-12; nil = off)
--   anim:Step(dt)                             -- advance and write the bones
--   anim:Destroy()                            -- bones back to rest

local DogAnimator = {}
DogAnimator.__index = DogAnimator

local WALK_RUN_SWITCH = 0.55 -- switch to Run above this fraction of the way from walk speed to run speed
local IDLE_BELOW = 0.35      -- studs/s (at the native scale) below which the dog stands
local FADE = 0.18            -- seconds for locomotion cross-fades
local VARIANT_FADE = 0.35    -- softer blend into and out of idle variants (sit, sniff, shake...)
local VARIANT_DELAY = { 6, 12 } -- seconds of plain Idle before the next variant

-- ------------------------------------------------------------------ quaternions as plain numbers (x, y, z, w)
local function qget(arr, frame)
	local i = frame * 4
	return arr[i + 1], arr[i + 2], arr[i + 3], arr[i + 4]
end

local function basis(a: Vector3, b: Vector3, c: Vector3): CFrame
	-- right-handed frame from three points: X along b->c, Y the part of b->a orthogonal to it
	local e1 = (c - b).Unit
	local v = a - b
	local e2 = (v - e1 * v:Dot(e1)).Unit
	local e3 = e1:Cross(e2)
	return CFrame.fromMatrix(Vector3.zero, e1, e2, e3)
end

local function vec(t)
	return Vector3.new(t[1], t[2], t[3])
end

-- ------------------------------------------------------------------ construction
function DogAnimator.fromBones(bones: { any }, data)
	local self = setmetatable({}, DogAnimator)
	self.data = data
	self.fps = data.fps
	self.byName = {}
	for _, b in bones do
		self.byName[b.Name] = b
	end

	-- the bones we drive, parents first; anything the import dropped is reported once and skipped
	self.order = {}
	local missing = {}
	for _, name in data.order do
		if self.byName[name] then
			table.insert(self.order, name)
		else
			table.insert(missing, name)
		end
	end
	if #missing > 0 then
		warn("[DogAnimator] bones missing from the imported rig: " .. table.concat(missing, ", "))
	end
	for _, need in { "DogRoot", "Hips", "Head" } do
		assert(self.byName[need], "[DogAnimator] the rig needs a bone named " .. need)
	end

	-- rest pose in the frame of the part that holds the skeleton (chain of Bone.CFrame; Transform is ignored)
	self.rest = {}
	self.isBoneParent = {}
	local function restOf(b)
		local r = self.rest[b.Name]
		if r then
			return r
		end
		local p = b.Parent
		if p and p:IsA("Bone") then
			r = restOf(p) * b.CFrame
			self.isBoneParent[b.Name] = true
		else
			r = b.CFrame
		end
		self.rest[b.Name] = r
		return r
	end
	for _, name in self.order do
		restOf(self.byName[name])
	end

	-- fit Blender model axes -> rig space: rotation M and scale s (Blender metres -> studs as imported)
	local R = data.rest
	local bb = basis(vec(R.DogRoot), vec(R.Hips), vec(R.Head))
	local rr = basis(self.rest.DogRoot.Position, self.rest.Hips.Position, self.rest.Head.Position)
	self.M = rr * bb:Inverse()
	self.Minv = self.M:Inverse()
	self.s = (self.rest.Head.Position - self.rest.Hips.Position).Magnitude / (vec(R.Head) - vec(R.Hips)).Magnitude
	-- the scale relative to what the clips were made for (speeds scale with it)
	self.scale = self.s / data.studsPerMetre

	-- check the fit on every bone: a mirrored or rebuilt skeleton would not line up
	local worst = 0
	local rootPos = self.rest.DogRoot.Position
	for _, name in self.order do
		local want = rootPos + self.M:VectorToWorldSpace((vec(R[name]) - vec(R.DogRoot)) * self.s)
		worst = math.max(worst, (self.rest[name].Position - want).Magnitude)
	end
	self.fitError = worst / self.s -- in Blender metres
	if self.fitError > 0.01 then
		warn(("[DogAnimator] the imported skeleton does not match the clip data (off by %.3f m); poses may look wrong")
			:format(self.fitError))
	end

	-- constant offsets of each bone head from its parent's rest frame (children ride on their parents)
	self.offset = {}
	for _, name in self.order do
		local parent = data.parents[name]
		if parent and self.rest[parent] then
			self.offset[name] = self.rest[parent]:PointToObjectSpace(self.rest[name].Position)
		end
	end

	-- idle variants: one-shot clips flagged idleVariant, played now and then while standing
	self.idleVariants = {}
	for name, clip in data.clips do
		if clip.idleVariant then
			table.insert(self.idleVariants, name)
		end
	end
	table.sort(self.idleVariants)
	self.variantDelay = { VARIANT_DELAY[1], VARIANT_DELAY[2] }
	self.idleClock = 0
	self.nextVariantAt = self:_rollDelay()

	self.tracks = {}
	self.mode = "ground" -- ground | crouch | jump | air | land
	self.locoName = nil
	self.locoRate = 1
	self.world = {}
	return self
end

function DogAnimator.new(model: Instance, data)
	local bones = {}
	for _, d in model:GetDescendants() do
		if d:IsA("Bone") then
			table.insert(bones, d)
		end
	end
	return DogAnimator.fromBones(bones, data)
end

-- ------------------------------------------------------------------ tracks
-- A track plays frames [from, to] of a clip; loops wrap, one-shots hold the last frame and call onEnd once.
function DogAnimator:_play(name, opts)
	opts = opts or {}
	local clip = self.data.clips[name]
	assert(clip, "no clip " .. tostring(name))
	local last = clip.loop and clip.frames or clip.frames - 1
	local track = {
		name = name,
		clip = clip,
		from = opts.from or 0,
		to = opts.to or last,
		time = opts.from or 0,
		rate = opts.rate or 1,
		loop = clip.loop and opts.from == nil and opts.to == nil,
		weight = opts.fade == 0 and 1 or 0,
		target = 1,
		fade = opts.fade or FADE,
		onEnd = opts.onEnd,
		ended = false,
	}
	for _, t in self.tracks do
		t.target = 0
		t.fade = opts.fade or FADE
	end
	table.insert(self.tracks, track)
	return track
end

function DogAnimator:_advance(dt)
	local keep = {}
	for _, t in self.tracks do
		if t.fade <= 0 then
			t.weight = t.target
		elseif t.weight < t.target then
			t.weight = math.min(t.target, t.weight + dt / t.fade)
		elseif t.weight > t.target then
			t.weight = math.max(t.target, t.weight - dt / t.fade)
		end
		t.time += dt * self.fps * t.rate
		if t.loop then
			t.time = t.from + (t.time - t.from) % (t.to - t.from)
		elseif t.time >= t.to then
			t.time = t.to
			if not t.ended then
				t.ended = true
				if t.onEnd then
					t.onEnd()
				end
			end
		end
		if t.weight > 0 or t.target > 0 then
			table.insert(keep, t)
		end
	end
	self.tracks = keep
end

-- ------------------------------------------------------------------ idle variants
function DogAnimator:_rollDelay()
	local d = self.variantDelay
	if not d then
		return math.huge
	end
	return d[1] + math.random() * (d[2] - d[1])
end

function DogAnimator:SetIdleVariantDelay(minSeconds: number?, maxSeconds: number?)
	self.variantDelay = minSeconds and { minSeconds, maxSeconds or minSeconds } or nil
	self.idleClock = 0
	self.nextVariantAt = self:_rollDelay()
end

function DogAnimator:_stopVariant()
	self.variantTrack = nil
	self.variantName = nil
	self.idleClock = 0
	self.nextVariantAt = self:_rollDelay()
end

function DogAnimator:PlayIdleVariant(name: string?)
	if self.mode ~= "ground" or #self.idleVariants == 0 then
		return nil
	end
	if not name then
		-- random, but never the same one twice in a row
		local pool = {}
		for _, n in self.idleVariants do
			if n ~= self.variantName and n ~= self.lastVariant then
				table.insert(pool, n)
			end
		end
		if #pool == 0 then
			pool = self.idleVariants
		end
		name = pool[math.random(1, #pool)]
	end
	local track
	track = self:_play(name, {
		fade = VARIANT_FADE,
		onEnd = function()
			if self.variantTrack == track then
				-- it ends on the standing pose: hand back to the Idle loop with a soft blend
				self:_stopVariant()
				self.locoName = nil
				self.locoFade = VARIANT_FADE
			end
		end,
	})
	self.variantTrack = track
	self.variantName = name
	self.lastVariant = name
	return track
end

-- ------------------------------------------------------------------ locomotion and jump states
function DogAnimator:SetLocomotion(speed: number)
	local clips = self.data.clips
	local v = speed / self.scale -- in the clips' native studs/s
	if self.mode ~= "ground" then
		self.pendingSpeed = v
		return
	end
	local walkV, runV = clips.Walk.speed, clips.Run.speed
	local name, rate
	if v < IDLE_BELOW then
		name, rate = "Idle", 1
	else
		local switch = walkV + (runV - walkV) * WALK_RUN_SWITCH
		-- a little hysteresis so the gait doesn't flicker at the threshold
		if self.locoName == "Run" then
			switch *= 0.9
		end
		if v >= switch then
			name, rate = "Run", math.clamp(v / runV, 0.7, 1.5)
		else
			name, rate = "Walk", math.clamp(v / walkV, 0.45, 1.9)
		end
	end
	if self.variantTrack then
		if name == "Idle" then
			return -- the variant is the idle for now
		end
		self:_stopVariant() -- started moving: leave the variant with a soft blend
		self.locoFade = VARIANT_FADE
	end
	if name ~= self.locoName or not self.locoTrack or self.locoTrack.target == 0 then
		self.locoName = name
		self.locoTrack = self:_play(name, { fade = self.locoFade })
		self.locoFade = nil
		if name == "Idle" then
			self.idleClock = 0
		end
	end
	self.locoTrack.rate = rate
end

function DogAnimator:_marker(key)
	local m = self.data.clips.Jump.markers
	return m[key][1], m[key][2]
end

function DogAnimator:Crouch()
	if self.mode ~= "ground" then
		return
	end
	self.mode = "crouch"
	self:_stopVariant()
	local a = self:_marker("takeoff")
	self.locoTrack = nil
	self:_play("Jump", { from = a, to = 9, fade = 0.08 })
end

function DogAnimator:Jump()
	if self.mode == "air" or self.mode == "jump" then
		return
	end
	local cued = self.mode == "crouch" -- otherwise no anticipation: start at the push-off
	self.mode = "jump"
	self:_stopVariant()
	self.locoTrack = nil
	local _, takeoffEnd = self:_marker("takeoff")
	local airFrom, airTo = self:_marker("air")
	local function air()
		if self.mode ~= "jump" then
			return
		end
		self.mode = "air"
		self:_play("Jump", { from = airFrom, to = airTo, fade = 0.05 })
	end
	if cued then
		-- continue the crouch track straight into the push-off
		local t = self.tracks[#self.tracks]
		if t and t.name == "Jump" then
			t.to = takeoffEnd
			t.ended = false
			t.rate = 1.6
			t.onEnd = air
			return
		end
	end
	self:_play("Jump", { from = 9, to = takeoffEnd, rate = 1.6, fade = 0.06, onEnd = air })
end

function DogAnimator:Fall()
	-- walked off a ledge: go straight to the airborne poses
	if self.mode == "ground" or self.mode == "land" then
		self.locoTrack = nil
		self:_stopVariant()
		local airFrom, airTo = self:_marker("air")
		self.mode = "air"
		self:_play("Jump", { from = math.floor((airFrom + airTo) / 2), to = airTo, fade = 0.12 })
	end
end

function DogAnimator:Land()
	if self.mode == "ground" or self.mode == "land" then
		return
	end
	self.mode = "land"
	local a, b = self:_marker("land")
	local moving = (self.pendingSpeed or 0) > self.data.clips.Walk.speed * 1.2
	self:_play("Jump", {
		from = a,
		to = moving and a + 5 or b, -- running on: only the absorb, then straight back into the gait
		fade = 0.05,
		onEnd = function()
			if self.mode == "land" then
				self.mode = "ground"
				self.locoName = nil
				self:SetLocomotion((self.pendingSpeed or 0) * self.scale)
			end
		end,
	})
end

-- ------------------------------------------------------------------ pose evaluation
local function sampleRot(clip, bone, time, loop)
	local arr = clip.rot[bone]
	if not arr then
		return 0, 0, 0, 1
	end
	local n = clip.frames
	local f0 = math.floor(time)
	local a = time - f0
	local f1 = f0 + 1
	if loop then
		f0 %= n
		f1 %= n
	else
		f0 = math.clamp(f0, 0, n - 1)
		f1 = math.clamp(f1, 0, n - 1)
	end
	local x0, y0, z0, w0 = qget(arr, f0)
	local x1, y1, z1, w1 = qget(arr, f1)
	if x0 * x1 + y0 * y1 + z0 * z1 + w0 * w1 < 0 then
		x1, y1, z1, w1 = -x1, -y1, -z1, -w1
	end
	return x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, z0 + (z1 - z0) * a, w0 + (w1 - w0) * a
end

local function sampleRoot(clip, time, loop)
	local arr = clip.root
	local n = clip.frames
	local f0 = math.floor(time)
	local a = time - f0
	local f1 = f0 + 1
	if loop then
		f0 %= n
		f1 %= n
	else
		f0 = math.clamp(f0, 0, n - 1)
		f1 = math.clamp(f1, 0, n - 1)
	end
	local i, j = f0 * 3, f1 * 3
	local x = arr[i + 1] + (arr[j + 1] - arr[i + 1]) * a
	local y = arr[i + 2] + (arr[j + 2] - arr[i + 2]) * a
	local z = arr[i + 3] + (arr[j + 3] - arr[i + 3]) * a
	if clip.physicsLift and z > 0 then
		z = 0 -- the Humanoid jump moves the body up; keep only the crouch/landing dips
	end
	return x, y, z
end

-- blended pose: {bone = CFrame rotation (Blender axes)}, root offset (Blender metres)
function DogAnimator:_blend()
	local total = 0
	for _, t in self.tracks do
		total += t.weight
	end
	local rot = {}
	local rx, ry, rz = 0, 0, 0
	if total <= 1e-4 then
		return rot, Vector3.zero
	end
	local norm = math.max(total, 1) -- weights below 1 in total blend toward the rest pose
	for _, name in self.order do
		local x, y, z, w = 0, 0, 0, math.max(0, 1 - total)
		for _, t in self.tracks do
			if t.weight > 0 then
				local qx, qy, qz, qw = sampleRot(t.clip, name, t.time, t.loop)
				if qx * x + qy * y + qz * z + qw * w < 0 then
					qx, qy, qz, qw = -qx, -qy, -qz, -qw
				end
				local k = t.weight / norm
				x += qx * k
				y += qy * k
				z += qz * k
				w += qw * k
			end
		end
		local len = math.sqrt(x * x + y * y + z * z + w * w)
		if len > 1e-6 then
			rot[name] = CFrame.new(0, 0, 0, x / len, y / len, z / len, w / len)
		end
	end
	for _, t in self.tracks do
		if t.weight > 0 then
			local x, y, z = sampleRoot(t.clip, t.time, t.loop)
			local k = t.weight / norm
			rx += x * k
			ry += y * k
			rz += z * k
		end
	end
	return rot, Vector3.new(rx, ry, rz)
end

-- write Bone.Transform for the blended pose
function DogAnimator:_apply(rot, rootOffset)
	local world = self.world
	local M, Minv = self.M, self.Minv
	for _, name in self.order do
		local bone = self.byName[name]
		local rest = self.rest[name]
		local d = rot[name]
		local dr = d and (M * d * Minv) or CFrame.identity
		local parent = self.data.parents[name]
		local pos
		if parent and world[parent] then
			pos = world[parent]:PointToWorldSpace(self.offset[name])
		else
			pos = rest.Position + M:VectorToWorldSpace(rootOffset * self.s)
		end
		local w = CFrame.new(pos) * dr * rest.Rotation
		world[name] = w
		-- bone world = parentWorld * Bone.CFrame * Transform
		local parentWorld = (parent and self.isBoneParent[name]) and world[parent] or CFrame.identity
		bone.Transform = (parentWorld * bone.CFrame):Inverse() * w
	end
end

function DogAnimator:Step(dt: number)
	if self.mode == "ground" and self.locoName == "Idle" and not self.variantTrack then
		self.idleClock += dt
		if self.idleClock >= self.nextVariantAt then
			self:PlayIdleVariant()
		end
	end
	self:_advance(dt)
	local rot, root = self:_blend()
	self:_apply(rot, root)
end

-- for tests and tools: show one frame of one clip with full weight
function DogAnimator:Pose(name: string, frame: number)
	local clip = self.data.clips[name]
	self.tracks = { { name = name, clip = clip, time = frame, rate = 0, loop = clip.loop, weight = 1, target = 1,
		fade = 0, from = 0, to = clip.frames - 1, ended = true } }
	local rot, root = self:_blend()
	self:_apply(rot, root)
end

function DogAnimator:Destroy()
	for _, name in self.order do
		self.byName[name].Transform = CFrame.identity
	end
	self.tracks = {}
end

return DogAnimator
