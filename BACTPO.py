local json = require("json")
local http = require("http")
local datetime = require("datetime")

local Bot = {}
Bot.__index = Bot

function Bot:new(token)
    local self = setmetatable({}, Bot)
    self.token = token
    self.base_url = "https://api.telegram.org/bot" .. token .. "/"
    self.users = {}
    self.numbers = {}
    return self
end

function Bot:request(method, data)
    local url = self.base_url .. method
    
    local options = {
        method = "POST",
        headers = {
            ["Content-Type"] = "application/json"
        }
    }
    
    if data then
        options.body = json.encode(data)
    end
    
    local response = http.request(url, options)
    if response then
        return json.decode(response.body)
    end
    return nil
end

function Bot:sendMessage(chat_id, text, buttons)
    local data = {
        chat_id = chat_id,
        text = text,
        parse_mode = "HTML"
    }
    
    if buttons then
        data.reply_markup = {
            inline_keyboard = buttons
        }
    end
    
    return self:request("sendMessage", data)
end

function Bot:answerCallback(callback_id, text)
    local data = {
        callback_query_id = callback_id,
        text = text or ""
    }
    return self:request("answerCallbackQuery", data)
end

function Bot:getUpdates(offset)
    local url = self.base_url .. "getUpdates"
    if offset then
        url = url .. "?offset=" .. offset .. "&timeout=30"
    else
        url = url .. "?timeout=30"
    end
    
    local response = http.get(url)
    if response then
        return json.decode(response.body)
    end
    return {ok = false, result = {}}
end

function Bot:startButtons()
    return {
        {
            {{text = "📱 Сдать номер", callback_data = "seller"}},
            {{text = "👤 Стать покупателем", callback_data = "buyer_code"}}
        }
    }
end

function Bot:buyerButtons()
    return {
        {
            {{text = "📋 Свободные", callback_data = "free"}},
            {{text = "🔍 Найти", callback_data = "find"}},
            {{text = "📦 Заказы", callback_data = "orders"}},
            {{text = "✅ Успешные", callback_data = "success"}}
        }
    }
end

function Bot:sellerButtons()
    return {
        {
            {{text = "➕ Добавить", callback_data = "add"}},
            {{text = "📊 Мои", callback_data = "my"}}
        }
    }
end

function Bot:statusButtons()
    local time = os.date("%H:%M")
    return {
        {
            {{text = "✅ Встал (" .. time .. ")", callback_data = "ok"}},
            {{text = "❌ Не встал (" .. time .. ")", callback_data = "fail"}}
        }
    }
end

function Bot:normalizePhone(phone)
    phone = phone:gsub("%s+", "")
    
    if phone:match("^%+7%d%d%d%d%d%d%d%d%d%d$") then
        return phone
    elseif phone:match("^8%d%d%d%d%d%d%d%d%d%d$") then
        return "+7" .. phone:sub(2)
    elseif phone:match("^7%d%d%d%d%d%d%d%d%d%d$") then
        return "+" .. phone
    end
    
    return nil
end

function Bot:handleMessage(msg)
    local chat_id = msg.chat.id
    local text = msg.text or ""
    text = text:gsub("^%s*(.-)%s*$", "%1")
    
    if text == "/start" then
        self:sendMessage(chat_id, "👋 <b>MAX БОТ</b>", self:startButtons())
        self.users[chat_id] = {role = "", state = ""}
        return
    end
    
    local user = self.users[chat_id] or {}
    local role = user.role or ""
    local state = user.state or ""
    
    if state == "code" then
        if text:lower() == "lolpop" then
            self.users[chat_id] = {role = "buyer", state = "menu"}
            self:sendMessage(chat_id, "✅ <b>Покупатель</b>", self:buyerButtons())
        else
            self:sendMessage(chat_id, "❌ Неверный код")
        end
        return
    end
    
    if role == "seller" and state == "add" then
        self:addNumber(chat_id, text)
    elseif role == "seller" and state == "wait" then
        self:sendCode(chat_id, text)
    elseif role == "buyer" and state == "find" then
        self:findNumber(chat_id, text)
    elseif role == "buyer" and state == "ask" then
        self:status(chat_id, text)
end

function Bot:handleCallback(callback)
    local chat_id = callback.message.chat.id
    local data = callback.data
    local callback_id = callback.id
    
    if data == "seller" then
        self.users[chat_id] = {role = "seller", state = "menu"}
        self:answerCallback(callback_id, "Сдатчик")
        self:sendMessage(chat_id, "📱 <b>Сдатчик</b>", self:sellerButtons())
    
    elseif data == "buyer_code" then
        self.users[chat_id].state = "code"
        self:answerCallback(callback_id, "Введите ")
        self:sendMessage(chat_id, "👤 Код: <code></code>")
    
    elseif data == "free" then
        local free = {}
        for phone, info in pairs(self.numbers) do
            if info.st == "free" then
                table.insert(free, "📱 <code>" .. phone .. "</code>")
            end
        end
        
        if #free > 0 then
            self:answerCallback(callback_id, "Свободных: " .. #free)
            local show = {}
            for i = 1, math.min(5, #free) do
                table.insert(show, free[i])
            end
            self:sendMessage(chat_id, "📋 <b>Свободные:</b>\n\n" .. table.concat(show, "\n"))
            
            local btns = {}
            for _, p in ipairs(show) do
                local phone = p:gsub("📱 <code>", ""):gsub("</code>", "")
                table.insert(btns, {{text = "Выбрать " .. phone, callback_data = "pick_" .. phone}})
            end
            
            if #btns > 0 then
                self:sendMessage(chat_id, "👇 Выберите:", btns)
            end
        else
            self:answerCallback(callback_id, "Нет")
            self:sendMessage(chat_id, "📭 Нет номеров")
        end
    
    elseif data == "find" then
        self.users[chat_id].state = "find"
        self:answerCallback(callback_id, "Введите номер")
        self:sendMessage(chat_id, "🔍 Номер (формат: +79991234567):")
    
    elseif data == "orders" then
        local orders = {}
        for phone, info in pairs(self.numbers) do
            if info.buyer == chat_id then
                local st = info.st or ""
                local t = info.t or ""
                if st == "busy" then
                    table.insert(orders, "📱 " .. phone .. " - ⏳ (" .. t .. ")")
                elseif st == "wait" then
                    table.insert(orders, "📱 " .. phone .. " - 📨 (" .. t .. ")")
                elseif st == "ok" then
                    table.insert(orders, "📱 " .. phone .. " - ✅ (" .. (info.ok_t or t) .. ")")
                elseif st == "fail" then
                    table.insert(orders, "📱 " .. phone .. " - ❌ (" .. (info.fail_t or t) .. ")")
                elseif st == "crash" then
                    table.insert(orders, "📱 " .. phone .. " - 💥 (" .. (info.crash_t or t) .. ")")
                end
            end
        end
        
        if #orders > 0 then
            self:answerCallback(callback_id, "Заказов: " .. #orders)
            self:sendMessage(chat_id, "📦 <b>Заказы:</b>\n\n" .. table.concat(orders, "\n"))
        else
            self:answerCallback(callback_id, "Нет")
            self:sendMessage(chat_id, "📭 Нет заказов")
        end
    
    elseif data == "success" then
        local success = {}
        for phone, info in pairs(self.numbers) do
            if info.buyer == chat_id and info.st == "ok" then
                table.insert(success, "📱 <code>" .. phone .. "</code>")
            end
        end
        
        if #success > 0 then
            self:answerCallback(callback_id, "Успешных: " .. #success)
            local show = {}
            for i = 1, math.min(5, #success) do
                table.insert(show, success[i])
            end
            self:sendMessage(chat_id, "✅ <b>Успешные:</b>\n\n" .. table.concat(show, "\n"))
            
            local btns = {}
            for _, p in ipairs(show) do
                local phone = p:gsub("📱 <code>", ""):gsub("</code>", "")
                table.insert(btns, {{text = "💥 " .. phone .. " слетел", callback_data = "crash_" .. phone}})
            end
            
            if #btns > 0 then
                self:sendMessage(chat_id, "👇 Слетели:", btns)
            end
        else
            self:answerCallback(callback_id, "Нет")
            self:sendMessage(chat_id, "✅ Нет успешных")
        end
    
    elseif data == "add" then
        self.users[chat_id].state = "add"
        self:answerCallback(callback_id, "Введите номер")
        self:sendMessage(chat_id, "➕ Номер для сдачи:")
    
    elseif data == "my" then
        local nums = {}
        for phone, info in pairs(self.numbers) do
            if info.seller == chat_id then
                local st = info.st or "free"
                local t = info.t or ""
                if st == "free" then
                    table.insert(nums, "📱 " .. phone .. " - 🟢 (" .. t .. ")")
                elseif st == "busy" then
                    table.insert(nums, "📱 " .. phone .. " - 🟡 (" .. t .. ")")
                elseif st == "wait" then
                    table.insert(nums, "📱 " .. phone .. " - 📨 (" .. t .. ")")
                elseif st == "ok" then
                    table.insert(nums, "📱 " .. phone .. " - ✅ (" .. (info.ok_t or t) .. ")")
                elseif st == "fail" then
                    table.insert(nums, "📱 " .. phone .. " - ❌ (" .. (info.fail_t or t) .. ")")
                elseif st == "crash" then
                    table.insert(nums, "📱 " .. phone .. " - 💥 (" .. (info.crash_t or t) .. ")")
                end
            end
        end
        
        if #nums > 0 then
            self:answerCallback(callback_id, "Номеров: " .. #nums)
            self:sendMessage(chat_id, "📊 <b>Номера:</b>\n\n" .. table.concat(nums, "\n"))
        else
            self:answerCallback(callback_id, "Нет")
            self:sendMessage(chat_id, "📭 Нет номеров")
        end
    
    elseif data:sub(1, 5) == "pick_" then
        local phone = data:sub(6)
        if self.numbers[phone] and self.numbers[phone].st == "free" then
            self:order(chat_id, phone)
        else
            self:answerCallback(callback_id, "❌ Занят")
            self:sendMessage(chat_id, "❌ Занят")
        end
    
    elseif data == "ok" then
        local phone = self.users[chat_id].phone
        if not phone then
            for p, info in pairs(self.numbers) do
                if info.buyer == chat_id and info.st == "wait" then
                    phone = p
                    break
                end
            end
        end
        
        if phone then
            local t = os.date("%H:%M")
            self.numbers[phone].st = "ok"
            self.numbers[phone].ok_t = t
            self.numbers[phone].t = t
            local seller = self.numbers[phone].seller
            if seller then
                self:sendMessage(seller, "🎉 <b>ВСТАЛ!</b>\n\n📱 " .. phone .. "\n🕒 " .. t)
            end
            self:sendMessage(chat_id, "✅ <b>Спасибо!</b>\n\n📱 " .. phone, self:buyerButtons())
            self.users[chat_id].phone = nil
            self.users[chat_id].state = "menu"
        end
    
    elseif data == "fail" then
        local phone = self.users[chat_id].phone
        if not phone then
            for p, info in pairs(self.numbers) do
                if info.buyer == chat_id and info.st == "wait" then
                    phone = p
                    break
                end
            end
        end
        
        if phone then
            local t = os.date("%H:%M")
            self.numbers[phone].st = "fail"
            self.numbers[phone].fail_t = t
            self.numbers[phone].t = t
            local seller = self.numbers[phone].seller
            if seller then
                self:sendMessage(seller, "❌ <b>НЕ ВСТАЛ</b>\n\n📱 " .. phone .. "\n🕒 " .. t)
            end
            self:sendMessage(chat_id, "❌ <b>Спасибо!</b>\n\n📱 " .. phone, self:buyerButtons())
            self.users[chat_id].phone = nil
            self.users[chat_id].state = "menu"
        end
    
    elseif data:sub(1, 6) == "crash_" then
        local phone = data:sub(7)
        if self.numbers[phone] and self.numbers[phone].buyer == chat_id then
            if self.numbers[phone].st == "ok" then
                local t = os.date("%H:%M")
                self.numbers[phone].st = "crash"
                self.numbers[phone].crash_t = t
                self.numbers[phone].t = t
                local seller = self.numbers[phone].seller
                if seller then
                    self:sendMessage(seller, "💥 <b>СЛЕТЕЛ!</b>\n\n📱 " .. phone .. "\n🕒 " .. t)
                end
                self:sendMessage(chat_id, "💥 <b>Отмечено!</b>\n\n📱 " .. phone, self:buyerButtons())
                self:answerCallback(callback_id, "Слетел")
            end
        end
    end
end

function Bot:addNumber(cid, text)
    local phone = self:normalizePhone(text)
    if not phone then
        self:sendMessage(cid, "❌ Неверно")
        return
    end
    local t = os.date("%H:%M")
    self.numbers[phone] = {seller = cid, st = "free", t = t}
    self.users[cid].state = "menu"
    self:sendMessage(cid, "✅ <code>" .. phone .. "</code> добавлен!", self:sellerButtons())
end

function Bot:order(buyer, phone)
    local seller = self.numbers[phone].seller
    local t = os.date("%H:%M")
    self.numbers[phone].st = "busy"
    self.numbers[phone].t = t
    self.numbers[phone].buyer = buyer
    self:sendMessage(buyer, "✅ <code>" .. phone .. "</code>\n⏳ Ждите...", self:buyerButtons())
    self:sendMessage(seller, "🎉 <b>ЗАКАЗ!</b>\n\n📱 " .. phone .. "\n👤 Ждет код", self:sellerButtons())
    self.users[seller].state = "wait"
    self.users[seller].phone = phone
end

function Bot:findNumber(buyer, text)
    local phone = self:normalizePhone(text)
    if not phone then
        self:sendMessage(buyer, "❌ Неверно")
        return
    end
    if self.numbers[phone] then
        if self.numbers[phone].st == "free" then
            self:order(buyer, phone)
        else
            self:sendMessage(buyer, "❌ " .. phone .. " занят")
        end
    else
        self:sendMessage(buyer, "❌ " .. phone .. " нет")
    end
    self.users[buyer].state = "menu"
end

function Bot:sendCode(seller, text)
    local code = text:gsub("^%s*(.-)%s*$", "%1")
    local phone = self.users[seller].phone
    if not phone or not self.numbers[phone] then
        self:sendMessage(seller, "❌ Ошибка")
        self.users[seller].state = "menu"
        return
    end
    local buyer = self.numbers[phone].buyer
    if not buyer then
        self:sendMessage(seller, "❌ Нет покупателя")
        self.users[seller].state = "menu"
        return
    end
    local t = os.date("%H:%M")
    self:sendMessage(buyer, "🎉 <b>КОД!</b>\n\n📱 " .. phone .. "\n🔢 <b>" .. code .. "</b>", self:statusButtons())
    self.users[buyer].phone = phone
    self.users[buyer].state = "ask"
    self:sendMessage(seller, "✅ <b>Отправлен!</b>\n\n📱 " .. phone .. "\n🔢 " .. code, self:sellerButtons())
    self.numbers[phone].st = "wait"
    self.numbers[phone].t = t
    self.numbers[phone].code = code
    self.users[seller].state = "menu"
end

function Bot:status(buyer, text)
    local phone = self.users[buyer].phone
    if not phone then
        for p, info in pairs(self.numbers) do
            if info.buyer == buyer and info.st == "wait" then
                phone = p
                break
            end
        end
    end
    if not phone then
        self:sendMessage(buyer, "❌ Ошибка")
        self.users[buyer].state = "menu"
        return
    end
    local txt_lower = text:lower()
    local t = os.date("%H:%M")
    if txt_lower:find("встал") and not txt_lower:find("не встал") then
        self.numbers[phone].st = "ok"
        self.numbers[phone].ok_t = t
        self.numbers[phone].t = t
        local seller = self.numbers[phone].seller
        if seller then
            self:sendMessage(seller, "🎉 <b>ВСТАЛ!</b>\n\n📱 " .. phone .. "\n🕒 " .. t)
        end
        self:sendMessage(buyer, "✅ <b>Спасибо!</b>\n\n📱 " .. phone, self:buyerButtons())
    elseif txt_lower:find("не встал") then
        self.numbers[phone].st = "fail"
        self.numbers[phone].fail_t = t
        self.numbers[phone].t = t
        local seller = self.numbers[phone].seller
        if seller then
            self:sendMessage(seller, "❌ <b>НЕ ВСТАЛ</b>\n\n📱 " .. phone .. "\n🕒 " .. t)
        end
        self:sendMessage(buyer, "❌ <b>Спасибо!</b>\n\n📱 " .. phone, self:buyerButtons())
    else
        self:sendMessage(buyer, "❓ Нажмите кнопку:", self:statusButtons())
        return
    end
    self.users[buyer].phone = nil
    self.users[buyer].state = "menu"
end

function Bot:run()
    print("🤖 Бот запущен: " .. os.date("%Y-%m-%d %H:%M:%S"))
    local last_update = 0
    
    while true do
        local updates = self:getUpdates(last_update)
        if updates and updates.ok then
            for _, update in ipairs(updates.result) do
                last_update = update.update_id + 1
                if update.callback_query then
                    self:handleCallback(update.callback_query)
                elseif update.message then
                    self:handleMessage(update.message)
                end
            end
        end
        os.sleep(0.1)
    end
end

-- Запуск бота
local token = "8489865823:AAFv2yJWKtCiw4iK6F__-W9nS8_Ex0BfY1g"
if token == "ВАШ_ТОКЕН" then
    io.write("Введите токен бота: ")
    token = io.read()
end

local bot = Bot:new(token)
bot:run()