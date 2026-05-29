# Децентралізована система захищеного файлообміну на приватному блокчейні

> *P2P-система для безпечного обміну файлами між вузлами мережі з використанням блокчейну, AES-256-GCM шифрування та Proof-of-Work консенсусу — без центрального сервера.*

---

## Автор

- **ПІБ**: Скриник Віктор Миколайович
- **Група**: ФЕІ-42
- **Керівник**: Ляшкевич В.Я., кандидат технічних наук, доцент 
- **Дата виконання**: 2026

---

## Загальна інформація

- **Тип проєкту**: Децентралізована P2P-система / Дослідницький проєкт
- **Мова програмування**: Python 3.11
- **Фреймворки / Бібліотеки**: Flask, cryptography (PyCA), socket, threading, unittest

---

## Опис функціоналу

- Автоматичне виявлення вузлів у локальній мережі (UDP Multicast + HTTP-сканування LAN)
- Наскрізне шифрування файлів (AES-256-GCM + RSA-2048 гібридна схема)
- Цифровий підпис кожного блоку (RSA-PKCS1v15-SHA256)
- Консенсус Proof-of-Work (SHA-256, ціль — 5 нулів у хеші)
- Самовідновлення мережі: heartbeat-пінги кожні 3 секунди, автоматичне видалення мертвих вузлів
- DES-симуляція масштабованості до 100 000 вузлів
- Веб-дашборд у реальному часі (Vanilla JS)
- 9 автоматизованих Mock-тестів критичного шляху

---

## Опис основних класів / файлів

| Клас / Файл | Призначення |
|---|---|
| `app.py` | Точка входу — Flask REST API + запуск фонових потоків вузла |
| `network/node.py` | Ядро P2P-вузла: сервер, клієнт, heartbeat, управління пірами |
| `network/discovery.py` | UDP Multicast та TCP-виявлення вузлів у LAN |
| `network/config.py` | Детерміноване призначення портів та реєстр пірів |
| `blockchain/block.py` | Структура блоку, обчислення SHA-256 хешу |
| `blockchain/chain.py` | Управління ланцюгом: PoW, валідація, вирішення форків |
| `blockchain/keys.py` | Генерація RSA-2048 ключів, підпис та верифікація |
| `security/encryption.py` | AES-256-GCM шифрування + RSA обгортання ключів |
| `files/handler.py` | Координація захищеної передачі файлів між вузлами |
| `analysis/des_simulation.py` | Дискретно-подієвий симулятор масштабованості (DES) |
| `analysis/traffic_simulator.py` | Генератор конкурентного навантаження для тестування |
| `analysis/logger.py` | Структурований JSON-логер подій вузла |
| `frontend/index.html` | SPA-дашборд: стан мережі, піри, блокчейн у реальному часі |
| `tests/test_critical_path.py` | 9 Mock-тестів критичного шляху системи |
| `start_cluster.ps1` | PowerShell-скрипт запуску N вузлів автоматично |
| `run_full_simulation.ps1` | Комплексна симуляція: кластер + трафік в один клік |

---

## Як запустити проєкт "з нуля"

### 1. Встановлення інструментів

- Python 3.11+
- pip

### 2. Клонування репозиторію

```bash
git clone https://github.com/Vitiaok/Diploma.git
cd Diploma/diploma_project
```

### 3. Встановлення залежностей

```bash
pip install flask cryptography requests
```

### 4. Запуск одного вузла

```bash
python app.py node1
```

Веб-інтерфейс відкриється за адресою: **http://localhost:5001**

### 5. Запуск кластеру (PowerShell)

```powershell
# Запустити 5 вузлів автоматично
.\start_cluster.ps1 -count 5

# Повна симуляція: 5 вузлів + 10 одночасних передач файлів по 100 КБ
.\run_full_simulation.ps1 -nodes 5 -transfers 10 -filesizeKB 100
```

### 6. Запуск через Docker

```bash
docker-compose up --scale node=5
```

---

## API Приклади

### Статус вузла

**GET /api/status**

```bash
curl http://localhost:5001/api/status
```

**Response:**
```json
{
  "status": "running",
  "node_id": "node1",
  "host": "192.168.1.10",
  "port": 6001,
  "peers_count": 4,
  "chain_length": 12,
  "public_key": "-----BEGIN PUBLIC KEY-----\n..."
}
```

---

### Відправка зашифрованого файлу

**POST /api/send_file**

```bash
curl -X POST http://localhost:5001/api/send_file \
  -F "file=@/path/to/secret.pdf"
```

**Response:**
```json
{
  "status": "success",
  "block_hash": "00000a3f...",
  "recipients": ["node2", "node3"]
}
```

---

### Отримати блокчейн

**GET /api/chain**

```bash
curl http://localhost:5001/api/chain
```

---

### Список активних пірів

**GET /api/peers**

```bash
curl http://localhost:5001/api/peers
```

---

## Інструкція для користувача

1. **Запустіть вузол** командою `python app.py node1` — вузол автоматично знайде інші вузли в мережі.

2. **Відкрийте дашборд** у браузері: `http://localhost:5001`
   - Панель показує кількість активних пірів, довжину блокчейну та публічний ключ вузла.

3. **Відправте файл**:
   - Натисніть кнопку `Send File` на дашборді
   - Оберіть файл — він автоматично зашифрується та відправиться всім підключеним вузлам

4. **Перегляд блокчейну**:
   - Кожна успішна передача файлу створює новий блок у ланцюзі
   - Блок містить SHA-256 хеш файлу, часову мітку та цифровий підпис

5. **Симуляція навантаження** (PowerShell):
   ```powershell
   .\run_full_simulation.ps1 -nodes 7 -transfers 15 -filesizeKB 250
   ```

---

## Приклади / скриншоти

(додайте зображення у папку `/screenshots/`)

- Головний дашборд з активними вузлами
- Відображення блокчейну після передачі файлів
- Консоль вузла під час симуляції навантаження
- Результати DES-симуляції у CSV

---

## Тестування

```bash
python -m unittest tests.test_critical_path
```

**Очікуваний результат:**
```
Ran 9 tests in ~9s
OK
```

| Тест | Що перевіряє |
|---|---|
| `test_blockchain_rejects_tampered_blocks` | Незмінність — підробка file_hash відхиляється |
| `test_proof_of_work_difficulty` | PoW генерує хеш з 5 нульовими символами |
| `test_consensus_fork_resolution` | Правило найдовшого ланцюга вирішує форки |
| `test_concurrency_race_condition` | RLock запобігає пошкодженню даних у 10 потоках |
| `test_missing_block_sync_trigger` | Блок з відсутнім predecessor відхиляється |
| `test_aes_encryption_decryption_flow` | AES-256-GCM шифрує/дешифрує без втрат даних |
| `test_rsa_signature_forgery` | Підроблений RSA-підпис відхиляється |
| `test_node_handles_connection_refused` | Мертві вузли видаляються автоматично |
| `test_discovery_handles_malformed_udp_packets` | Битий JSON не крашить модуль виявлення |

---

## Проблеми і рішення

| Проблема | Рішення |
|---|---|
| Вузли не знаходять один одного | Перевірити, чи увімкнено UDP Multicast у брандмауері Windows |
| `WinError 10061` у логах | Нормальна поведінка — вузол намагається підключитись до вже вимкненого піра |
| `Port already in use` | Змініть `node_id` або закрийте попередній процес Python |
| Docker-вузли не бачать один одного | Переконайтесь, що всі контейнери у спільній docker network |

---

## Використані джерела / література

- Nakamoto S. Bitcoin: A Peer-to-Peer Electronic Cash System. 2008.
- Python Cryptographic Authority. [cryptography](https://cryptography.io/en/latest/) library Documentation.
- Pallets Projects. [Flask](https://flask.palletsprojects.com) Web Framework Documentation.
- NIST FIPS 197. Advanced Encryption Standard (AES). 2001.
- Tanenbaum A.S., Van Steen M. Distributed Systems: Principles and Paradigms. 3rd ed. Pearson. 2017.
- Zheng Z. et al. An Overview of Blockchain Technology: Architecture, Consensus, and Future Trends. IEEE BigData Congress. 2017.
- Antonopoulos A.M. Mastering Bitcoin: Programming the Open Blockchain. 2nd ed. O'Reilly. 2017.

---

## Screenshots
