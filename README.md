# MQ Solar Local by PATCoder97

Phát triển và duy trì bởi [PATCoder97](https://github.com/PATCoder97).

Custom integration Home Assistant chỉ giao tiếp trực tiếp với thiết bị trong
mạng LAN. Repo này không chứa Cloud API, WebSocket, API token hoặc Device ID
Cloud.

## Tính năng

- Quét thiết bị Mạnh Quân Solar trong cùng subnet `/24`.
- Cho phép nhập IP/hostname thủ công.
- Poll dữ liệu local mỗi giây.
- Hỗ trợ MPPT Charger và Grid-tie Inverter theo API firmware hiện có.
- Không cần Internet sau khi cài đặt.
- Có entity nút reboot Wi-Fi, reboot bộ sạc và đọc cấu hình sạc.
- Có entity chỉnh chế độ sạc, dòng tối đa và điện áp tối đa.
- Nhận telemetry MQTT mỗi giây khi broker khả dụng; HTTP local vẫn là dự phòng.
- Hiển thị chẩn đoán Wi-Fi SSID/RSSI và MQTT host/port/topic/trạng thái kết nối.

## Điều khiển MQTT local

Các action sau được lấy từ firmware v2.3.3:

- `mqsolar_local.restart`: reboot module Wi-Fi ESP8266.
- `mqsolar_local.reboot_charge`: reboot bộ điều khiển sạc STM32.
- `mqsolar_local.get_charger_config`: đọc cấu hình sạc và trả response JSON.
- `mqsolar_local.set_charger_config`: ghi `chargeMode`, `maxCurrent`,
  `maxVoltage`; bắt buộc đặt `confirm: true`.

Home Assistant và module phải kết nối cùng MQTT broker. Integration tự phát hiện
base topic từ luồng dữ liệu MQTT theo Device ID rồi gửi lệnh vào `<base>/cmd`.
Thiết bị v2.3.3 đã kiểm tra thực tế với cấu hình `topic: 45a` sử dụng
`45a_45a/<deviceId>/data` và `45a_45a/<deviceId>/cmd`, khác với prefix
`mppt_charger` nhúng trong firmware. Nếu không thấy dữ liệu MQTT, integration mới
dùng mẫu `topic_topic/<deviceId>` đã xác nhận trên MPPT v2.3.3 làm fallback.

Các ô chỉnh dòng, áp và chế độ chỉ khả dụng sau khi integration đọc được phản
hồi `charger_config_sync`. Nhấn **Đọc cấu hình sạc** nếu chúng đang hiển thị
Unavailable. Nút **Khởi động lại Wi-Fi** chỉ reboot ESP8266, không bật quyền
chỉnh dòng sạc.

Ba chế độ sạc xác nhận từ giao diện firmware là `0` (Pin Lithium), `1` (Ắc quy
chì-axit) và `2` (Nguồn Inverter).

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

Trên SSH/Linux, có thể cấu hình bằng một lệnh `curl`:

```bash
curl --connect-timeout 5 --max-time 15 -X POST \
  "http://DEVICE_IP/api/mqtt/config" \
  -H "Content-Type: application/json" \
  -d '{"host":"MQTT_BROKER_IP","port":1883,"user":"MQTT_USER","pass":"MQTT_PASSWORD","topic":"45a"}'
```

Thay `DEVICE_IP`, `MQTT_BROKER_IP`, `MQTT_USER` và `MQTT_PASSWORD` bằng thông
tin thực tế. Không sao chép dấu nhắc `$` hoặc `>` của terminal. Module sẽ lưu cấu
hình và tự khởi động lại sau khi trả về `MQTT saved! Restarting...`.

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
3. Tải **MQ Solar Local by PATCoder97** và khởi động lại Home Assistant.

Logo được đóng gói cục bộ trong integration và hiển thị từ Home Assistant
2026.3 trở lên. Sau khi cập nhật, cần khởi động lại Home Assistant và có thể cần
refresh mạnh trình duyệt để xóa ảnh placeholder đã cache.

## Cài thủ công

Copy thư mục `custom_components/mqsolar_local` vào
`/config/custom_components/mqsolar_local`, sau đó khởi động lại Home Assistant.

Vào **Cài đặt → Thiết bị & Dịch vụ → Thêm tích hợp → MQ Solar Local by PATCoder97** và chọn
**Quét mạng nội bộ** hoặc **Nhập IP thủ công**.

Nên cấu hình DHCP reservation cho module để IP không thay đổi.
