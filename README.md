# Mạnh Quân Solar — local only

Custom integration Home Assistant chỉ giao tiếp trực tiếp với thiết bị trong
mạng LAN. Repo này không chứa Cloud API, WebSocket, API token hoặc Device ID
Cloud.

## Tính năng

- Quét thiết bị Mạnh Quân Solar trong cùng subnet `/24`.
- Cho phép nhập IP/hostname thủ công.
- Poll dữ liệu local mỗi giây.
- Hỗ trợ MPPT Charger và Grid-tie Inverter theo API firmware hiện có.
- Không cần Internet sau khi cài đặt.

## Điều khiển MQTT local

Các action sau được lấy từ firmware v2.3.3:

- `mqsolar_local.restart`: reboot module Wi-Fi ESP8266.
- `mqsolar_local.reboot_charge`: reboot bộ điều khiển sạc STM32.
- `mqsolar_local.get_charger_config`: đọc cấu hình sạc và trả response JSON.
- `mqsolar_local.set_charger_config`: ghi `chargeMode`, `maxCurrent`,
  `maxVoltage`; bắt buộc đặt `confirm: true`.

Home Assistant và module phải kết nối cùng MQTT broker. Firmware tạo command
topic theo dạng `mppt_charger_<topic_code>/<deviceId>/cmd`; mã topic mặc định
trong firmware v2.3.3 là `45a`. Nếu đã đổi trường `topic` qua
`/api/mqtt/config`, hãy nhập đúng giá trị đó khi chạy action.

Nếu module vẫn đang dùng broker Cloud mặc định, cấu hình nó sang broker MQTT nội
bộ trước. Ví dụ PowerShell (request này làm module lưu cấu hình rồi reboot):

```powershell
$body = @{
  host = "192.168.1.10"
  port = 1883
  user = "mqsolar"
  pass = "your-password"
  topic = "45a"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://DEVICE_IP/api/mqtt/config" `
  -ContentType "application/json" `
  -Body $body
```

Ví dụ:

```yaml
action: mqsolar_local.set_charger_config
data:
  config_entry_id: 01ABCDEF...
  topic_code: 45a
  charge_mode: 1
  max_current: 45.0
  max_voltage: 14.4
  confirm: true
```

Các giới hạn `200 A` và `100 V` trong form chỉ là giới hạn kỹ thuật để chặn dữ
liệu bất thường, không phải thông số an toàn của phần cứng. Người dùng phải chọn
giá trị phù hợp với model bộ sạc và ắc quy.

## Yêu cầu firmware

Thiết bị cần trả JSON từ:

- `GET /api/status`
- `GET /api/charger/data` đối với MPPT, hoặc `GET /api/data` đối với inverter.

Firmware `MPPT_WIFI_0905_v2.3.3.bin` đáp ứng hai endpoint MPPT.

## Cài bằng HACS

1. Mở **HACS → Integrations → Custom repositories**.
2. Thêm URL GitHub của repo này với loại **Integration**.
3. Tải **Mạnh Quân Solar** và khởi động lại Home Assistant.

## Cài thủ công

Copy thư mục `custom_components/mqsolar_local` vào
`/config/custom_components/mqsolar_local`, sau đó khởi động lại Home Assistant.

Vào **Cài đặt → Thiết bị & Dịch vụ → Thêm tích hợp → Mạnh Quân Solar** và chọn
**Quét mạng nội bộ** hoặc **Nhập IP thủ công**.

Nên cấu hình DHCP reservation cho module để IP không thay đổi.
