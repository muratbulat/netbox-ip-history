# NetBox IP History

[English](README.md) | **Türkçe**

Dokümantasyon: [GitHub Wiki](https://github.com/muratbulat/netbox-ip-history/wiki)

[![PyPI](https://img.shields.io/pypi/v/netbox-ip-history.svg)](https://pypi.org/project/netbox-ip-history/)
[![PyPI - Python Sürümleri](https://img.shields.io/pypi/pyversions/netbox-ip-history.svg)](https://pypi.org/project/netbox-ip-history/)
[![CI](https://github.com/muratbulat/netbox-ip-history/actions/workflows/ci.yml/badge.svg)](https://github.com/muratbulat/netbox-ip-history/actions/workflows/ci.yml)
[![Lisans](https://img.shields.io/badge/lisans-Apache--2.0-blue.svg)](LICENSE)

<p align="center">
  <img src="docs/assets/icon.svg" alt="NetBox IP History icon" width="120" height="120" />
</p>

NetBox IP History `0.3.1`, NetBox `core.ObjectChange` kayıtlarını ve GestioIP, phpIPAM, CSV, JSON/JSONL gibi dış kaynaklardan alınan geçmişi tek bir IP zaman çizelgesinde birleştiren NetBox eklentisidir. Dış kayıtlar kaynak kimliğini, kaynak kullanıcısını, `ImportJob`, zamanı, kapsamı ve tam `raw_data` görüntüsünü korur.

**Lisans:** Apache-2.0

## Ekran Görüntüleri

### IP Zaman Çizelgesi ve Yaşam Döngüsü Arama
<p align="center">
  <img src="docs/assets/screenshots/timeline_search.png" alt="IP Zaman Çizelgesi ve Arama" width="100%" />
</p>

### Çoklu Kaynak Karşılaştırma (Source Reconciliation)
<p align="center">
  <img src="docs/assets/screenshots/source_comparison.png" alt="Çoklu Kaynak Karşılaştırma" width="100%" />
</p>

### Geçmiş Veri İçe Aktarma (CSV / JSON / JSONL)
<p align="center">
  <img src="docs/assets/screenshots/import_data.png" alt="Veri İçe Aktarma" width="100%" />
</p>

### İçe Aktarma İşleri ve Geri Alma (Rollback)
<p align="center">
  <img src="docs/assets/screenshots/import_jobs.png" alt="İçe Aktarma İşleri" width="100%" />
</p>

### Kaynak Destek Matrisi
<p align="center">
  <img src="docs/assets/screenshots/source_support_matrix.png" alt="Kaynak Destek Matrisi" width="100%" />
</p>

## Uyumluluk

| Plugin | NetBox | Python | Durum |
| --- | --- | --- | --- |
| 0.3.x | 4.4.x (v4.4.10) | 3.11 | CI'de doğrulandı |
| 0.3.x | 4.5.x (v4.5.10) | 3.12 | CI'de doğrulandı |
| 0.3.x | 4.6.x (v4.6.8) | 3.12, 3.14 | CI'de doğrulandı; 3.14 öncelikli olarak doğrulanmış kombinasyondur |

Bu aralıklar ve doğrulanmış sürümler için kanıt matrisi [COMPATIBILITY.md](COMPATIBILITY.md) dosyasında yer almaktadır.

## Bağımlılıklar

NetBox runtime'ı dışında ek zorunlu Python bağımlılığı: **Yok**. Django, PostgreSQL ve Redis gereksinimleri NetBox tarafından sağlanır. Dış IPAM bağlantısı isteğe bağlıdır; doğrulanmış yol yönetici tarafından sağlanan dosya exportlarıdır.

## Amaç ve özellikler

Bir IP adresinin şimdi ve geçmişte hangi cihaz, VM, arayüz veya MAC tarafından kullanıldığını, ne zaman değiştiğini ve bilginin hangi IPAM/DDI/CMDB sisteminden geldiğini gösterir. Geçmiş kayıtları yerel `HistoricalIPEvent` modelinde saklanır; sahte NetBox `ObjectChange` kayıtları oluşturulmaz. IP adresleri IPv4/IPv6 için kanonikleştirilir, VRF kapsamı korunur, silinmiş nesnelerin adları denetim görüntülerinden saklanır ve tekrar çalıştırılan içe aktarımlar SHA-256 parmak izi ile tekilleştirilir.

## Kaynaklar ve destek düzeyi

GestioIP, phpIPAM, RackTables, GLPI, Device42, Infoblox, BlueCat, Micetro, EfficientIP, NIPAP, TeemIP/iTop, SolarWinds, ManageEngine, Microsoft IPAM, başka bir NetBox, Nautobot, Ralph, Generic SQL ve Generic/Other IPAM için bağımsız adapter modülleri bulunur. Destek matrisi `/plugins/ip-history/sources/support/` adresinde capability bildirimlerinden üretilir. GestioIP, phpIPAM, Generic CSV/JSON ve portable exchange format doğrulanmış dosya yollarıdır. Diğer vendor adapterleri, belirli ürün sürümüne göre `EXPORT` veya `EXPERIMENTAL` durumundadır; doğrulanmamış API veya audit geçmişi uydurulmaz.

## Kurulum

### PyPI

```bash
source /opt/netbox/venv/bin/activate
pip install netbox-ip-history
```

### GitHub

```bash
cd /opt && git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history && pip install -e .
```

Kurulum, güncelleme, devre dışı bırakma ve kaldırma için tam talimatlar (NetBox yapılandırması, migration ve doğrulama dahil): **[docs/INSTALLATION.md](docs/INSTALLATION.md)** — Türkçe sürüm: **[docs/INSTALLATION_TR.md](docs/INSTALLATION_TR.md)**.

Eklenti `/plugins/ip-history/` adresinde ve doğrudan NetBox IP adresi (`ipam.ipaddress`) detay sayfalarında kullanılabilir olacaktır.

## Yapılandırma ve güvenlik

Tüm web arayüzleri ve API endpoint'leri `raise_exception=True` ile katı Django model izinlerine tabidir (yetkisiz veya anonim erişimler HTTP 403 Forbidden ile engellenir):

- `view_historicalipevent`: Zaman çizelgesi arama (`/plugins/ip-history/`), olay detayı, kaynak karşılaştırma ve IP adresi detay paneli erişimi.
- `add_historicalipevent`: Veri içe aktarma arayüzü (`/plugins/ip-history/import/`).
- `delete_historicalipevent`: İçe aktarılan işleri geri alma (`/plugins/ip-history/import-jobs/<pk>/rollback/`).
- `view_importjob`: İçe aktarma denetim kayıtları ve detayları (`/plugins/ip-history/import-jobs/`).
- `view_importsource`: Kaynak matrisi ve adaptör yetenekleri (`/plugins/ip-history/sources/support/`).

`ImportSource` kaydında kaynak adı, türü, timezone, field mapping, support level, capability, priority ve authority bilgileri tutulur. Parolalar, tokenlar ve authentication header değerleri modelde, tarayıcıda veya loglarda tutulmaz; environment veya `PLUGINS_CONFIG` secret referansları kullanılır. Kaynak SQL bağlantıları yalnızca read-only olmalıdır.

## Kullanım ve içe aktarma

`/plugins/ip-history/?ip=10.222.1.33` adresinde IP, VRF, kaynak, event type, tarih, owner, hostname ve kullanıcı filtrelenebilir. `/plugins/ip-history/import/` dosya yükleme, kaynak mapping ve dry-run önizlemesi sağlar. Dry-run historical event yazmaz. Sonuçlar `/plugins/ip-history/import-jobs/` altında incelenir. `/plugins/ip-history/compare/?ip=10.222.1.33` yalnızca kaynak karşılaştırması yapar; veriyi değiştirmez.

GestioIP ve phpIPAM CSV/JSON dışa aktarımları, Generic CSV/TSV ve Generic JSON/JSONL mapping ile alınabilir. UTF-8 BOM, quoted fields, delimiter ve kaynak timezone desteklenir. Portable format örneği:

```json
{
  "format": "netbox-ip-history",
  "version": 1,
  "source": {"type": "other", "name": "Legacy IPAM"},
  "records": [{"ip": "10.222.1.33", "timestamp": "2024-01-01T10:00:00+03:00", "owner_name": "APP01", "event_type": "assigned"}]
}
```

### Yönetim Komutları (CLI)

Büyük içe aktarmalar ve yerel NetBox loglarının senkronizasyonu için komut satırı araçları:

```bash
# Dış kaynaktan dosya içe aktarma
python netbox/manage.py import_ip_history --source gestioip --file /data/history.csv --history-only --dry-run
python netbox/manage.py import_ip_history --source phpipam --file /data/export.json --history-only

# Geçmiş NetBox ObjectChange kayıtlarını HistoricalIPEvent modeline senkronize etme
python netbox/manage.py sync_netbox_ip_history --dry-run
python netbox/manage.py sync_netbox_ip_history
```

## REST API Endpoint'leri

NetBox REST API endpoint'leri `/api/plugins/ip-history/` altında yer alır (standart NetBox izinleriyle korunur):

- `GET /api/plugins/ip-history/events/`: Geçmiş IP olaylarını listeleme ve filtreleme.
- `GET /api/plugins/ip-history/jobs/`: İçe aktarma işlerini izleme ve denetleme.
- `GET /api/plugins/ip-history/sources/`: Tanımlı kaynak profillerini listeleme.

## Mimari, arayüz ve özellikler

Adapter registry, capability/inspection sözleşmesi ve normalize DTO katmanı vendor kodunu timeline/persistence motorundan ayırır. VRF, network view, IP space ve address space gibi kapsamlar açık mapping olmadan birleştirilmez. Discovery/observation, assignment olarak yorumlanmaz. İndeksler `ip_address` ve `timestamp` sorgularını hedefler; büyük kaynaklarda CLI ve gelecekteki streaming adapterleri kullanılmalıdır.

Plugin özellikleri:
- NetBox sol menüsünde doğrudan üst menü (**IP History**) ve alt menüler (Timeline & Search, Source Comparison, Import Data, Import Jobs, Source Matrix).
- Genel "Plugins" menüsünü kirletmeden, temiz ve bağımsız sol menü entegrasyonu.
- NetBox IP adresi (`ipam.ipaddress`) detay sayfasında doğrudan **IP History** butonu ve geçmiş paneli entegrasyonu (`template_content.py`).
- NetBox 4.x Global Arama (Global Search) ile tam entegrasyon.
- Bootstrap 5 ve NetBox temasına tam uyumlu modern kartlar, renkli olay rozetleri (event badges), istatistik özetleri ve JSON snapshot görüntüleyicisi.

## Destek

Bug ve feature request: [GitHub Issues](https://github.com/muratbulat/netbox-ip-history/issues). Genel sorular: [GitHub Discussions](https://github.com/muratbulat/netbox-ip-history/discussions). Güvenlik: [SECURITY.md](SECURITY.md) ve GitHub Security Advisories.

## Geliştirme, katkı ve lisans

Geliştirme kuralları için [CONTRIBUTING.md](CONTRIBUTING.md), güvenlik bildirimi için [SECURITY.md](SECURITY.md) ve [LICENSE](LICENSE) dosyasına bakın. Proje Apache-2.0 lisanslıdır.