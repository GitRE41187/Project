# วิธี deploy Backend (ASP.NET) ไปที่ Render.com

คู่มือนี้อธิบายการนำ **backend-aspnet** ขึ้น **Render** เป็น Web Service (แผนฟรี) เพื่อนำเสนอโปรเจกต์หรือให้ Raspberry Pi ชี้ `SERVER_URL` มาที่ URL บนอินเทอร์เน็ต

> **ฐานข้อมูล:** โปรเจกต์ใช้ **PostgreSQL** (Npgsql) — บน Render สามารถสร้าง **PostgreSQL ฟรี** ได้ในตัว (New → PostgreSQL) แล้วใช้ connection string จากแดชบอร์ด

---

## สิ่งที่ต้องมีก่อน

1. โค้ดอยู่บน **GitHub** (หรือ Git provider ที่ Render รองรับ)
2. **ฐานข้อมูล PostgreSQL** ที่เข้าถึงได้จากอินเทอร์เน็ต (บน Render สร้าง instance ใหม่แล้วใช้ Internal/External URL ตามที่ต้องการ)
3. รัน schema บน DB นั้นแล้ว (ไฟล์ `database/schema.sql`) — ถ้าผู้ให้บริการสร้าง database ว่างให้แล้ว ให้รันเฉพาะคำสั่ง `CREATE TABLE` เป็นต้นไปในไฟล์ (ข้ามบรรทัด `CREATE DATABASE` ใน comment ด้านบนของไฟล์)

---

## 1. เตรียม Connection String สำหรับ PostgreSQL

ตัวอย่างรูปแบบ (ปรับ host, user, password, ชื่อ DB ให้ตรงกับผู้ให้บริการหรือ Render):

```text
Host=<host>;Port=5432;Database=field_control;Username=<user>;Password=<password>;SSL Mode=Require;
```

ถ้า Render แสดง **Internal Database URL** สำหรับ Web Service บนเครือข่ายเดียวกัน ให้ใช้ตามเอกสาร Render — สำหรับเครื่อง local หรือเชื่อมจากภายนอกใช้ **External** URL.

---

## 2. สร้าง Web Service บน Render

1. เข้า [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
2. เชื่อม repository ที่มีโปรเจกต์นี้
3. ตั้งค่าดังนี้ (แนะนำให้ตั้ง **Root Directory** เป็นโฟลเดอร์ backend เพื่อ build ง่าย)

| รายการ | ค่าแนะนำ |
|--------|----------|
| **Name** | ชื่อที่ต้องการ (จะได้ URL แบบ `https://<name>.onrender.com`) |
| **Region** | เลือกใกล้ที่สุด |
| **Branch** | `main` หรือ branch ที่ deploy |
| **Root Directory** | `backend-aspnet` |
| **Runtime** | **Native** (ไม่ใช้ Docker ในเส้นทางนี้) |
| **Build Command** | `dotnet publish -c Release -o publish` |
| **Start Command** | `cd publish && ASPNETCORE_URLS=http://0.0.0.0:$PORT dotnet backend-aspnet.dll` |

> Render จะตั้งตัวแปร **`PORT`** ให้อัตโนมัติ — ต้องให้แอปฟังที่ `0.0.0.0` และพอร์ตนี้ (คำสั่งด้านบนทำให้ ASP.NET Core ใช้พอร์ตจาก `PORT`)

---

## 3. ตั้งค่า Environment Variables

ในแท็บ **Environment** ของ Web Service ให้เพิ่มอย่างน้อยดังนี้:

| Key | ค่า / หมายเหตุ |
|-----|----------------|
| `ASPNETCORE_ENVIRONMENT` | `Production` |
| `ConnectionStrings__Default` | connection string PostgreSQL แบบบรรทัดเดียว (ดูข้อ 1) |
| `Jwt__Secret` | สตริงยาวอย่างน้อย 32 ตัวอักษร — **ห้ามใช้ค่า default จาก repo** |
| `ClientUrl` | URL ของแอปบน Render เช่น `https://<ชื่อ-service>.onrender.com` — ใช้กับ CORS (ต้องตรง scheme + host กับที่ผู้ใช้เปิดเว็บ) |

คีย์แบบ `Section__Key` เป็นรูปแบบมาตรฐานของ ASP.NET Core สำหรับ override `appsettings.json`

ตัวเลือกอื่นที่มีใน `appsettings.json` (ถ้าต้องการ override):

- `UploadDir` — โฟลเดอร์อัปโหลด (บน Render ไฟล์จะหายเมื่อ redeploy ถ้าไม่ใช้ดิสก์ถาวร — สำหรับโชว์งานอาจพอใช้)
- `MaxFileSize` — ขนาดไฟล์สูงสุด (เป็น string ตัวเลข)

---

## 4. Deploy และตรวจสอบ

1. บันทึกแล้วรอ build — ดู **Logs** ถ้า build หรือ start ล้มเหลว
2. เปิด `https://<ชื่อ-service>.onrender.com` — ควรเห็นหน้า frontend
3. ทดสอบ health: `GET https://<ชื่อ-service>.onrender.com/api/health` — ควรได้ JSON `status: OK`

---

## 5. เชื่อม Raspberry Pi

บน Raspberry Pi ตั้งค่าให้ชี้ไปที่ Backend บน Render:

```bash
export SERVER_URL=https://<ชื่อ-service>.onrender.com
```

จากนั้นรัน `python app.py` ตาม README — SignalR จะเชื่อมไปที่ `{SERVER_URL}/hubs/robot`

> ใช้ **HTTPS** ตาม URL ที่ Render ให้ (ไม่ใช้ `http://` ถ้า Render redirect ไป HTTPS)

---

## 6. ข้อจำกัดของแผนฟรีบน Render

- **Cold start:** ถ้าไม่มีคนใช้นาน แอปอาจ “หลับ” — การเปิดครั้งแรกอาจช้า **30–60 วินาที** — ควรเปิดลิงก์ทิ้งไว้ก่อนนำเสนอ
- **ดิสก์ ephemeral:** ไฟล์ใน `UploadDir` อาจไม่คงอยู่หลัง restart/redeploy
- **PostgreSQL ฟรี:** มีข้อจำกัดด้านพื้นที่และ connection — ตรวจ quota ในแดชบอร์ด Render

---

## 7. ทางเลือก: Deploy ด้วย Docker

ถ้าต้องการควบคุม runtime ด้วย Docker ให้สร้าง `Dockerfile` ที่ repo (หรือใน `backend-aspnet`) แล้วบน Render เลือก **Docker** แทน Native — ตั้ง **Dockerfile Path** และคำสั่งให้ process ฟังที่พอร์ตจากตัวแปร `PORT` (เช่น entrypoint ที่ export `ASPNETCORE_URLS=http://0.0.0.0:$PORT` ก่อน `dotnet backend-aspnet.dll`)

รายละเอียด image ฐานและ multi-stage build ให้อ้างอิง [เอกสาร Microsoft สำหรับ containerize ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/docker/building-net-docker-images)

---

## สรุป Checklist

- [ ] PostgreSQL พร้อม schema จาก `database/schema.sql`
- [ ] Web Service: Root `backend-aspnet`, build + start ตามข้อ 2
- [ ] ตั้ง `ConnectionStrings__Default`, `Jwt__Secret`, `ClientUrl`
- [ ] ทดสอบ `/` และ `/api/health`
- [ ] ตั้ง `SERVER_URL` บน Raspberry Pi เป็น `https://<ชื่อ>.onrender.com`
