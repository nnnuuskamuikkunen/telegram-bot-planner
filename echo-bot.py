import telebot

bot = telebot.TeleBot("8059208448:AAFnzPAfwvrfehwl9JvP7JacTpVE3yGK6jc", parse_mode=None)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Чего тебе надобно, старче?")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
	bot.reply_to(message, message.text)

bot.infinity_polling()
