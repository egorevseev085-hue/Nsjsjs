import json, time, urllib.request
from datetime import datetime

class MaxBot:
    def __init__(self, token):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}/"
        self.users = {}
        self.nums = {}
    
    def req(self, method, data=None):
        url = self.base + method
        try:
            if data:
                b = json.dumps(data).encode('utf-8')
                r = urllib.request.Request(url, data=b)
                r.add_header('Content-Type', 'application/json')
            else:
                r = urllib.request.Request(url)
            with urllib.request.urlopen(r, timeout=30) as res:
                return json.loads(res.read().decode('utf-8'))
        except:
            return None
    
    def send(self, cid, text, buttons=None):
        data = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
        if buttons: data["reply_markup"] = {"inline_keyboard": buttons}
        return self.req("sendMessage", data)
    
    def ans(self, cb_id, text=""):
        return self.req("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})
    
    def updates(self, offset=None):
        url = self.base + "getUpdates"
        if offset: url += f"?offset={offset}&timeout=30"
        else: url += "?timeout=30"
        try:
            with urllib.request.urlopen(url, timeout=35) as r:
                return json.loads(r.read().decode('utf-8'))
        except:
            return {"ok": False, "result": []}
    
    def start_buttons(self):
        return [
            [{"text": "📱 Сдать номер", "callback_data": "seller"}],
            [{"text": "👤 Стать покупателем", "callback_data": "buyer_code"}]
        ]
    
    def buyer_buttons(self):
        return [
            [{"text": "📋 Свободные", "callback_data": "free"}],
            [{"text": "🔍 Найти", "callback_data": "find"}],
            [{"text": "📦 Заказы", "callback_data": "orders"}],
            [{"text": "✅ Успешные", "callback_data": "success"}]
        ]
    
    def seller_buttons(self):
        return [
            [{"text": "➕ Добавить", "callback_data": "add"}],
            [{"text": "📊 Мои", "callback_data": "my"}]
        ]
    
    def status_buttons(self):
        now = datetime.now().strftime('%H:%M')
        return [
            [{"text": f"✅ Встал ({now})", "callback_data": "ok"}],
            [{"text": f"❌ Не встал ({now})", "callback_data": "fail"}]
        ]
    
    def process_msg(self, msg):
        cid = msg["chat"]["id"]
        text = msg.get("text", "").strip()
        
        if text == "/start":
            self.send(cid, "👋 <b>MAX БОТ</b>\nВыберите:", self.start_buttons())
            self.users[cid] = {"role": "", "state": ""}
            return
        
        user = self.users.get(cid, {})
        role = user.get("role")
        state = user.get("state")
        
        if state == "code":
            if text.lower() == "lolpop":
                self.users[cid] = {"role": "buyer", "state": "menu"}
                self.send(cid, "✅ <b>Вы покупатель!</b>", self.buyer_buttons())
            else:
                self.send(cid, "❌ Неверный код")
            return
        
        if role == "seller" and state == "add":
            self.add_number(cid, text)
        elif role == "seller" and state == "wait":
            self.send_sms_code(cid, text)
        elif role == "buyer" and state == "find":
            self.find_number(cid, text)
        elif role == "buyer" and state == "ask":
            self.process_status(cid, text)
    
    def process_callback(self, callback):
        cid = callback["message"]["chat"]["id"]
        data = callback["data"]
        cb_id = callback["id"]
        
        if data == "seller":
            self.users[cid] = {"role": "seller", "state": "menu"}
            self.ans(cb_id, "Вы сдатчик")
            self.send(cid, "📱 <b>Вы сдатчик номеров</b>", self.seller_buttons())
        
        elif data == "buyer_code":
            self.users[cid]["state"] = "code"
            self.ans(cb_id, "Введите код")
            self.send(cid, "👤 Введите код: <code></code>")
        
        elif data == "free":
            free_nums = []
            for phone, info in self.nums.items():
                if info.get("status") == "free":
                    time_added = info.get("time", "?")
                    free_nums.append(f"📱 <code>{phone}</code> ({time_added})")
            
            if free_nums:
                self.ans(cb_id, f"Свободных: {len(free_nums)}")
                show = free_nums[:5]
                self.send(cid, "📋 <b>Свободные номера:</b>\n\n" + "\n".join(show))
                
                buttons = []
                for p in show:
                    phone = p.split(" ")[1].replace("<code>", "").replace("</code>", "").split("(")[0].strip()
                    buttons.append([{"text": f"Выбрать {phone}", "callback_data": f"pick_{phone}"}])
                
                if buttons:
                    self.send(cid, "👇 Выберите:", buttons)
            else:
                self.ans(cb_id, "Нет свободных")
                self.send(cid, "📭 Нет свободных номеров")
        
        elif data == "find":
            self.users[cid]["state"] = "find"
            self.ans(cb_id, "Введите номер")
            self.send(cid, "🔍 Введите номер (формат: +79991234567):")
        
        elif data == "orders":
            orders = []
            for phone, info in self.nums.items():
                if info.get("buyer_id") == cid:
                    status = info.get("status", "")
                    time_status = info.get("status_time", "?")
                    if status == "busy":
                        orders.append(f"📱 {phone} - ⏳ Ожидает ({time_status})")
                    elif status == "done":
                        orders.append(f"📱 {phone} - 📨 Получил код ({time_status})")
                    elif status == "success":
                        success_time = info.get("success_time", "?")
                        orders.append(f"📱 {phone} - ✅ Встал ({success_time})")
                    elif status == "failed":
                        failed_time = info.get("failed_time", "?")
                        orders.append(f"📱 {phone} - ❌ Не встал ({failed_time})")
                    elif status == "crashed":
                        crash_time = info.get("crash_time", "?")
                        orders.append(f"📱 {phone} - 💥 Слетел ({crash_time})")
            
            if orders:
                self.ans(cb_id, f"Заказов: {len(orders)}")
                self.send(cid, "📦 <b>Ваши заказы:</b>\n\n" + "\n".join(orders))
            else:
                self.ans(cb_id, "Нет заказов")
                self.send(cid, "📭 Нет заказов")
        
        elif data == "success":
            success_nums = []
            for phone, info in self.nums.items():
                if info.get("buyer_id") == cid and info.get("status") == "success":
                    success_time = info.get("success_time", "?")
                    success_nums.append(f"📱 <code>{phone}</code> (встал: {success_time})")
            
            if success_nums:
                self.ans(cb_id, f"Успешных: {len(success_nums)}")
                show = success_nums[:5]
                self.send(cid, "✅ <b>Успешные номера:</b>\n\n" + "\n".join(show))
                
                buttons = []
                for p in show:
                    phone = p.split(" ")[1].replace("<code>", "").replace("</code>", "").split("(")[0].strip()
                    buttons.append([{"text": f"💥 {phone} слетел", "callback_data": f"crash_{phone}"}])
                
                if buttons:
                    self.send(cid, "👇 Отметьте слетевшие:", buttons)
            else:
                self.ans(cb_id, "Нет успешных")
                self.send(cid, "✅ Нет успешных номеров")
        
        elif data == "add":
            self.users[cid]["state"] = "add"
            self.ans(cb_id, "Введите номер")
            self.send(cid, "➕ Введите номер для сдачи:")
        
        elif data == "my":
            seller_nums = []
            for phone, info in self.nums.items():
                if info.get("seller_id") == cid:
                    status = info.get("status", "free")
                    time_status = info.get("status_time", info.get("time", "?"))
                    
                    if status == "free":
                        seller_nums.append(f"📱 {phone} - 🟢 Свободен ({time_status})")
                    elif status == "busy":
                        seller_nums.append(f"📱 {phone} - 🟡 В работе ({time_status})")
                    elif status == "done":
                        seller_nums.append(f"📱 {phone} - 📨 Код отправлен ({time_status})")
                    elif status == "success":
                        success_time = info.get("success_time", "?")
                        seller_nums.append(f"📱 {phone} - ✅ Успех ({success_time})")
                    elif status == "failed":
                        failed_time = info.get("failed_time", "?")
                        seller_nums.append(f"📱 {phone} - ❌ Не встал ({failed_time})")
                    elif status == "crashed":
                        crash_time = info.get("crash_time", "?")
                        seller_nums.append(f"📱 {phone} - 💥 Слетел ({crash_time})")
            
            if seller_nums:
                self.ans(cb_id, f"Номеров: {len(seller_nums)}")
                self.send(cid, "📊 <b>Ваши номера:</b>\n\n" + "\n".join(seller_nums))
            else:
                self.ans(cb_id, "Нет номеров")
                self.send(cid, "📭 Нет номеров")
        
        elif data.startswith("pick_"):
            phone = data.replace("pick_", "")
            if phone in self.nums and self.nums[phone]["status"] == "free":
                self.order_number(cid, phone)
            else:
                self.ans(cb_id, "❌ Уже занят")
                self.send(cid, "❌ Номер уже занят")
        
        elif data == "ok":
            phone = self.users[cid].get("current_phone")
            if not phone:
                for p, info in self.nums.items():
                    if info.get("buyer_id") == cid and info.get("status") == "done":
                        phone = p
                        break
            
            if phone:
                now_time = datetime.now().strftime('%H:%M')
                self.nums[phone]["status"] = "success"
                self.nums[phone]["success_time"] = now_time
                self.nums[phone]["status_time"] = now_time
                
                seller_id = self.nums[phone].get("seller_id")
                if seller_id:
                    self.send(seller_id, f"🎉 <b>НОМЕР ВСТАЛ!</b>\n\n📱 {phone}\n🕒 {now_time}")
                
                self.send(cid, f"✅ <b>Спасибо!</b>\n\n📱 {phone}\n✅ Встал в {now_time}", self.buyer_buttons())
                
                if "current_phone" in self.users[cid]:
                    self.users[cid]["current_phone"] = None
                self.users[cid]["state"] = "menu"
        
        elif data == "fail":
            phone = self.users[cid].get("current_phone")
            if not phone:
                for p, info in self.nums.items():
                    if info.get("buyer_id") == cid and info.get("status") == "done":
                        phone = p
                        break
            
            if phone:
                now_time = datetime.now().strftime('%H:%M')
                self.nums[phone]["status"] = "failed"
                self.nums[phone]["failed_time"] = now_time
                self.nums[phone]["status_time"] = now_time
                
                seller_id = self.nums[phone].get("seller_id")
                if seller_id:
                    self.send(seller_id, f"❌ <b>НЕ ВСТАЛ</b>\n\n📱 {phone}\n🕒 {now_time}")
                
                self.send(cid, f"❌ <b>Спасибо!</b>\n\n📱 {phone}\n❌ Не встал в {now_time}", self.buyer_buttons())
                
                if "current_phone" in self.users[cid]:
                    self.users[cid]["current_phone"] = None
                self.users[cid]["state"] = "menu"
        
        elif data.startswith("crash_"):
            phone = data.replace("crash_", "")
            if phone in self.nums and self.nums[phone].get("buyer_id") == cid:
                if self.nums[phone]["status"] == "success":
                    now_time = datetime.now().strftime('%H:%M')
                    self.nums[phone]["status"] = "crashed"
                    self.nums[phone]["crash_time"] = now_time
                    self.nums[phone]["status_time"] = now_time
                    
                    seller_id = self.nums[phone].get("seller_id")
                    if seller_id:
                        self.send(seller_id, f"💥 <b>СЛЕТЕЛ!</b>\n\n📱 {phone}\n🕒 {now_time}")
                    
                    self.send(cid, f"💥 <b>Отмечено!</b>\n\n📱 {phone}\n💥 Слетел в {now_time}", self.buyer_buttons())
                    self.ans(cb_id, "Номер отмечен как слетевший")
    
    def normalize_phone(self, phone):
        phone = phone.strip()
        if phone.startswith('+7') and len(phone) == 12 and phone[1:].isdigit():
            return phone
        elif phone.startswith('8') and len(phone) == 11 and phone.isdigit():
            return '+7' + phone[1:]
        elif phone.startswith('7') and len(phone) == 11 and phone.isdigit():
            return '+' + phone
        return None
    
    def add_number(self, cid, text):
        phone = self.normalize_phone(text)
        if not phone:
            self.send(cid, "❌ Неверный формат")
            return
        
        now_time = datetime.now().strftime('%H:%M')
        self.nums[phone] = {
            "seller_id": cid,
            "status": "free",
            "time": now_time,
            "status_time": now_time
        }
        
        self.users[cid]["state"] = "menu"
        self.send(cid, f"✅ Номер <code>{phone}</code> добавлен!\n🕒 {now_time}", self.seller_buttons())
    
    def order_number(self, buyer_id, phone):
        seller_id = self.nums[phone]["seller_id"]
        now_time = datetime.now().strftime('%H:%M')
        
        self.nums[phone]["status"] = "busy"
        self.nums[phone]["status_time"] = now_time
        self.nums[phone]["buyer_id"] = buyer_id
        
        self.send(buyer_id, f"✅ Заказан номер <code>{phone}</code>\n⏳ Ждите код...\n🕒 {now_time}", self.buyer_buttons())
        
        self.send(seller_id,
            f"🎉 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
            f"📱 Номер: {phone}\n"
            f"🕒 {now_time}\n"
            f"👤 Покупатель ждет код\n\n"
            f"Что делать:\n"
            f"1. ждмте когда придёт код!\n"
            f"2. увидите SMS\n"
            f"3. Введите код сюда"
        )
        
        self.users[seller_id]["state"] = "wait"
        self.users[seller_id]["current_phone"] = phone
    
    def find_number(self, buyer_id, text):
        phone = self.normalize_phone(text)
        if not phone:
            self.send(buyer_id, "❌ Неверный формат")
            return
        
        if phone in self.nums:
            if self.nums[phone]["status"] == "free":
                self.order_number(buyer_id, phone)
            else:
                self.send(buyer_id, f"❌ Номер {phone} занят")
        else:
            self.send(buyer_id, f"❌ Номер {phone} не найден")
        
        self.users[buyer_id]["state"] = "menu"
    
    def send_sms_code(self, seller_id, text):
        code = text.strip()
        phone = self.users[seller_id].get("current_phone")
        
        if not phone or phone not in self.nums:
            self.send(seller_id, "❌ Ошибка")
            self.users[seller_id]["state"] = "menu"
            return
        
        buyer_id = self.nums[phone].get("buyer_id")
        if not buyer_id:
            self.send(seller_id, "❌ Покупатель не найден")
            self.users[seller_id]["state"] = "menu"
            return
        
        now_time = datetime.now().strftime('%H:%M')
        self.nums[phone]["status"] = "done"
        self.nums[phone]["status_time"] = now_time
        self.nums[phone]["code"] = code
        
        self.send(buyer_id, 
            f"🎉 <b>SMS-КОД ПОЛУЧЕН!</b>\n\n"
            f"📱 Номер: <code>{phone}</code>\n"
            f"🔢 Код: <b>{code}</b>\n"
            f"🕒 {now_time}\n\n"
            f"✅ Используйте код",
            self.status_buttons()
        )
        
        self.users[buyer_id]["current_phone"] = phone
        self.users[buyer_id]["state"] = "ask"
        
        self.send(seller_id, 
            f"✅ <b>Код отправлен!</b>\n\n"
            f"📱 {phone}\n"
            f"🔢 {code}\n"
            f"🕒 {now_time}"
        )
        
        self.users[seller_id]["state"] = "menu"
    
    def process_status(self, buyer_id, text):
        phone = self.users[buyer_id].get("current_phone")
        if not phone:
            for p, info in self.nums.items():
                if info.get("buyer_id") == buyer_id and info.get("status") == "done":
                    phone = p
                    break
        
        if not phone:
            self.send(buyer_id, "❌ Ошибка")
            self.users[buyer_id]["state"] = "menu"
            return
        
        text_lower = text.lower()
        now_time = datetime.now().strftime('%H:%M')
        
        if "встал" in text_lower and "не встал" not in text_lower:
            self.nums[phone]["status"] = "success"
            self.nums[phone]["success_time"] = now_time
            self.nums[phone]["status_time"] = now_time
            
            seller_id = self.nums[phone].get("seller_id")
            if seller_id:
                self.send(seller_id, f"🎉 <b>НОМЕР ВСТАЛ!</b>\n\n📱 {phone}\n🕒 {now_time}")
            
            self.send(buyer_id, f"✅ <b>Спасибо!</b>\n\n📱 {phone}\n✅ Встал в {now_time}", self.buyer_buttons())
        
        elif "не встал" in text_lower:
            self.nums[phone]["status"] = "failed"
            self.nums[phone]["failed_time"] = now_time
            self.nums[phone]["status_time"] = now_time
            
            seller_id = self.nums[phone].get("seller_id")
            if seller_id:
                self.send(seller_id, f"❌ <b>НЕ ВСТАЛ</b>\n\n📱 {phone}\n🕒 {now_time}")
            
            self.send(buyer_id, f"❌ <b>Спасибо!</b>\n\n📱 {phone}\n❌ Не встал в {now_time}", self.buyer_buttons())
        else:
            self.send(buyer_id, "❓ Нажмите кнопку:", self.status_buttons())
            return
        
        if "current_phone" in self.users[buyer_id]:
            self.users[buyer_id]["current_phone"] = None
        self.users[buyer_id]["state"] = "menu"
    
    def run(self):
        print(f"🤖 Бот запущен {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        last_update = 0
        
        while True:
            try:
                updates = self.updates(last_update)
                if updates.get("ok"):
                    for update in updates["result"]:
                        last_update = update["update_id"] + 1
                        if "callback_query" in update:
                            self.process_callback(update["callback_query"])
                        elif "message" in update:
                            self.process_msg(update["message"])
                time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n🛑 Бот остановлен")
                break
            except Exception as e:
                print(f"Ошибка: {e}")
                time.sleep(5)

if __name__ == "__main__":
    TOKEN= "8489865823:AAFv2yJWKtCiw4iK6F__-W9nS8_Ex0BfY1g"
    if TOKEN == "ВАШ_ТОКЕН":
        TOKEN = input("Введите токен бота: ").strip()
    
    bot = MaxBot(TOKEN)
    bot.run()