-- Minimal Vector3 / CFrame for running DogAnimator under the plain luau CLI (tests only).
-- Only what the animator uses; semantics follow Roblox (column vectors, CFrame * CFrame, CFrame * Vector3).

local V = {}
V.__index = function(v, k)
	if k == "X" then
		return v[1]
	elseif k == "Y" then
		return v[2]
	elseif k == "Z" then
		return v[3]
	elseif k == "Magnitude" then
		return math.sqrt(v[1] * v[1] + v[2] * v[2] + v[3] * v[3])
	elseif k == "Unit" then
		local m = math.sqrt(v[1] * v[1] + v[2] * v[2] + v[3] * v[3])
		return setmetatable({ v[1] / m, v[2] / m, v[3] / m }, V)
	end
	return V[k]
end
local function v3(x, y, z)
	return setmetatable({ x or 0, y or 0, z or 0 }, V)
end
V.__add = function(a, b)
	return v3(a[1] + b[1], a[2] + b[2], a[3] + b[3])
end
V.__sub = function(a, b)
	return v3(a[1] - b[1], a[2] - b[2], a[3] - b[3])
end
V.__unm = function(a)
	return v3(-a[1], -a[2], -a[3])
end
V.__mul = function(a, b)
	if type(a) == "number" then
		return v3(a * b[1], a * b[2], a * b[3])
	elseif type(b) == "number" then
		return v3(a[1] * b, a[2] * b, a[3] * b)
	end
	return v3(a[1] * b[1], a[2] * b[2], a[3] * b[3])
end
V.__div = function(a, b)
	return v3(a[1] / b, a[2] / b, a[3] / b)
end
function V.Dot(a, b)
	return a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
end
function V.Cross(a, b)
	return v3(a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1])
end
Vector3 = { new = v3, zero = v3(0, 0, 0), yAxis = v3(0, 1, 0) }

-- CFrame: r = rotation matrix rows {r00,r01,r02, r10,..., r22}, p = position
local C = {}
local function cf(r, p)
	return setmetatable({ r = r, p = p }, C)
end
C.__index = function(c, k)
	if k == "Position" then
		return c.p
	elseif k == "Rotation" then
		return cf(c.r, v3(0, 0, 0))
	end
	return C[k]
end
local function rmul(a, b)
	local o = {}
	for i = 0, 2 do
		for j = 0, 2 do
			o[i * 3 + j + 1] = a[i * 3 + 1] * b[j + 1] + a[i * 3 + 2] * b[3 + j + 1] + a[i * 3 + 3] * b[6 + j + 1]
		end
	end
	return o
end
local function rvec(r, v)
	return v3(r[1] * v[1] + r[2] * v[2] + r[3] * v[3], r[4] * v[1] + r[5] * v[2] + r[6] * v[3],
		r[7] * v[1] + r[8] * v[2] + r[9] * v[3])
end
local function rT(r)
	return { r[1], r[4], r[7], r[2], r[5], r[8], r[3], r[6], r[9] }
end
C.__mul = function(a, b)
	if getmetatable(b) == V then
		return rvec(a.r, b) + a.p
	end
	return cf(rmul(a.r, b.r), rvec(a.r, b.p) + a.p)
end
function C.Inverse(c)
	local t = rT(c.r)
	return cf(t, -rvec(t, c.p))
end
function C.PointToWorldSpace(c, v)
	return rvec(c.r, v) + c.p
end
function C.PointToObjectSpace(c, v)
	return rvec(rT(c.r), v - c.p)
end
function C.VectorToWorldSpace(c, v)
	return rvec(c.r, v)
end
local I = { 1, 0, 0, 0, 1, 0, 0, 0, 1 }
local function quat(x, y, z, w)
	local n = math.sqrt(x * x + y * y + z * z + w * w)
	x, y, z, w = x / n, y / n, z / n, w / n
	return {
		1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
		2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
		2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y),
	}
end
CFrame = {
	identity = cf(I, v3(0, 0, 0)),
	new = function(a, b, c, qx, qy, qz, qw)
		if a == nil then
			return cf(I, v3(0, 0, 0))
		elseif type(a) == "table" then
			return cf(I, a)
		elseif qx ~= nil then
			return cf(quat(qx, qy, qz, qw), v3(a, b, c))
		end
		return cf(I, v3(a, b, c))
	end,
	fromMatrix = function(p, x, y, z)
		z = z or x:Cross(y)
		return cf({ x[1], y[1], z[1], x[2], y[2], z[2], x[3], y[3], z[3] }, p)
	end,
	_quat = quat,
}

function warn(...)
	print("WARN", ...)
end
