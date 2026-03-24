# วิธี deploy Backend (ASP.NET) ไปที่ Render.com

คู่มือนี้อธิบายการนำ **backend-aspnet** ขึ้น **Render** เป็น Web Service (แผนฟรี) เพื่อนำเสนอโปรเจกต์หรือให้ Raspberry Pi ชี้ `SERVER_URL` มาที่ URL บนอินเทอร์เน็ต

> **ฐานข้อมูล:** โปรเจกต์ใช้ **PostgreSQL** (Npgsql) — บน Render สร้าง **PostgreSQL ฟรี** ได้ (New → PostgreSQL) แล้วใช้ connection string จากแดชบอร์ด

---

## ทำไมต้องใช้ Docker บน Render

บน Render **ไม่มีตัวเลือก runtime ชื่อ Native / ASP.NET Core** แบบเดิมแล้ว — รายการ runtime มักจะเป็นกลุ่มภาษา/แพลตฟอร์มทั่วไป และ **คำแนะนำของ Render สำหรับแอป .NET คือ deploy ผ่าน Docker** โปรเจกต์นี้มี Dockerfile สองแบบที่ build ได้เหมือนกัน: **`Dockerfile` ที่ root ของ repo** (เหมาะกับ Render ค่า default) และ **`backend-aspnet/Dockerfile`** (ใช้เมื่อตั้ง Root Directory เป็น `backend-aspnet`)

---

## สิ่งที่ต้องมีก่อน

1. โค้ดอยู่บน **GitHub** (หรือ Git provider ที่ Render รองรับ)
2. **PostgreSQL** ที่เข้าถึงได้ (สร้างบน Render หรือที่อื่น)
3. รัน schema บน DB แล้ว (ไฟล์ `database/schema.sql`)

---

## 1. เตรียม Connection String สำหรับ PostgreSQL

ตัวอย่างรูปแบบ Npgsql (ปรับ host, user, password, ชื่อ DB):

```text
Host=<host>;Port=5432;Database=field_control;Username=<user>;Password=<password>;SSL Mode=Require;
```

ถ้า Web Service กับ PostgreSQL อยู่บน Render เครือข่ายเดียวกัน ใช้ **Internal Database URL** ตามแดชบอร์ดได้ — ถ้าเชื่อมจากเครื่องอื่นใช้ **External** URL

### แก้ `Name or service not known` (Npgsql / Kestrel)

ข้อความนี้แปลว่า **แก้ DNS ไม่ได้จากค่า `Host`** — ไม่ใช่ user/password ผิด

สาเหตุที่พบบ่อย:

- ใส่ **ชื่อ instance สั้นๆ** (เช่น `myPGDB` ใน `render.yaml`) แทน **hostname จริง** แบบ `dpg-xxxxx-a.<region>-postgres.render.com`
- คัดลอก connection string ไม่ครบ หรือมีช่องว่าง/เครื่องหมายพิเศษใน `Host`

**แนวทางบน Render**

1. ไปที่ **PostgreSQL** ในแดชบอร์ด → คัดลอก **External Database URL** (หรือ Internal ถ้า Web Service กับ DB อยู่บน Render และใช้ internal network ตามเอกสาร Render)
2. ตั้งเป็น environment variable **`DATABASE_URL`** (รูปแบบ `postgresql://user:pass@host:5432/dbname`) — backend รองรับและจะใช้ **ก่อน** `ConnectionStrings__Default`
3. ถ้ายังตั้ง `ConnectionStrings__Default` ไว้ด้วยมือ ให้ตรวจว่า `Host=` ตรงกับ hostname ในหน้า Postgres จริงๆ ไม่ใช่ชื่อที่ตั้งเองใน Blueprint อย่างเดียว

---

## 2. สร้าง Web Service ด้วย Docker

1. เข้า [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
2. เชื่อม repository ที่มีโปรเจกต์นี้
3. ตั้งค่าหลักดังนี้

| รายการ | ค่าแนะนำ |
|--------|----------|
| **Name** | ชื่อที่ต้องการ → URL `https://<name>.onrender.com` |
| **Region** | ใกล้ที่สุด (เช่น Singapore) |
| **Branch** | `main` หรือ branch ที่ deploy |
| **Root Directory** | *(เว้นว่าง)* หรือไม่ตั้ง — **แนะนำ** ให้ใช้คู่กับ `Dockerfile` ที่ root |
| **Runtime / Environment** | **Docker** |
| **Dockerfile Path** | `./Dockerfile` หรือ `Dockerfile` (ชี้ไฟล์ที่ **root ของ repo**) |

**Dockerfile ใน `backend-aspnet/`** ต้องใช้ **build context = root ของ repo** (มีโฟลเดอร์ `database/`) — บน Render ให้ **Root Directory ว่าง** แล้วตั้ง **Dockerfile Path** เป็น `backend-aspnet/Dockerfile` หรือใช้ `./Dockerfile` ที่ root แทน

**ทางเลือก (monorepo):** ถ้าตั้ง **Root Directory** เป็น `backend-aspnet` อย่างเดียว โดยไม่รวม `database/` ใน context การ build จะล้มเหลว — ใช้ Root ว่าง + path ตามด้านบน

แอปจะ **ตรวจตาราง `users` ตอนสตาร์ท** — ถ้ายังไม่มีจะรัน `database/schema.sql` ที่ฝังใน assembly อัตโนมัติ (ยังควรรัน schema บน DB production ด้วยตนเองเมื่อ deploy ครั้งแรกถ้าต้องการควบคุมเอง)

**ไม่ต้องใส่ Build Command / Start Command แบบ `dotnet publish` เอง** — build อยู่ใน Dockerfile แล้ว

---

## 3. ตั้งค่า Environment Variables

ในแท็บ **Environment** ของ Web Service:

| Key | ค่า / หมายเหตุ |
|-----|----------------|
| `ASPNETCORE_ENVIRONMENT` | `Production` |
| `DATABASE_URL` | *(แนะนำ)* คัดลอกจากหน้า PostgreSQL บน Render (`postgresql://...`) — แอปอ่านค่านี้ก่อน |
| `ConnectionStrings__Default` | ทางเลือก: Npgsql แบบ `Host=...;Port=5432;...` — ใช้เมื่อไม่มี `DATABASE_URL` |
| `Jwt__Secret` | อย่างน้อย 32 ตัวอักษร — **ห้ามใช้ค่า default จาก repo** |
| `ClientUrl` | `https://<ชื่อ-service>.onrender.com` — ใช้กับ CORS |

คีย์ `Section__Key` เป็นรูปแบบมาตรฐานของ ASP.NET Core

ตัวเลือกอื่น: `UploadDir`, `MaxFileSize` (ดู `appsettings.json`)

---

## 4. Deploy และตรวจสอบ

1. บันทึกแล้วรอ build — ดู **Logs** ถ้า Docker build หรือ start ล้มเหลว
2. เปิด `https://<ชื่อ-service>.onrender.com`
3. ทดสอบ `GET .../api/health` — ควรได้ `status: OK`

---

## 5. เชื่อม Raspberry Pi

```bash
export SERVER_URL=https://<ชื่อ-service>.onrender.com
```

จากนั้นรัน `python app.py` — SignalR ไปที่ `{SERVER_URL}/hubs/robot`  
ใช้ **HTTPS** ตามที่ Render ให้

---

## 6. ข้อจำกัดแผนฟรี

- **Cold start** ครั้งแรกอาจช้า ~30–60 วินาที
- **ดิสก์ ephemeral** — ไฟล์อัปโหลดอาจหายหลัง redeploy
- **PostgreSQL ฟรี** — มี quota ตามแดชบอร์ด

---

## 7. Blueprint (render.yaml) — Docker

ถ้าใช้ [Infrastructure as Code](https://docs.render.com/docs/infrastructure-as-code) โปรดอ้างอิง [Blueprint spec](https://docs.render.com/docs/blueprint-spec) — โดยทั่วไปกำหนด `runtime: docker`, `dockerfilePath`, และ `rootDir` (หรือ path ให้ตรงกับโครง repo)

---

## สรุป Checklist

- [ ] PostgreSQL + รัน `database/schema.sql`
- [ ] Web Service: **Docker**, Dockerfile Path `./Dockerfile` (root ของ repo) — หรือ Root `backend-aspnet` + Path `Dockerfile` โดย**ไม่มีช่องว่าง**
- [ ] `ConnectionStrings__Default`, `Jwt__Secret`, `ClientUrl`
- [ ] ทดสอบ `/` และ `/api/health`
- [ ] Raspberry Pi: `SERVER_URL=https://<ชื่อ>.onrender.com`
