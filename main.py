import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
import requests
import json
import random
import string
import os


class ProfileManager:
    def __init__(self, fivesim_token, country, service, operator, domain):
        self.fivesim_token = fivesim_token
        self.country = country
        self.service = service
        self.operator = operator
        self.domain = domain
        self.redeem_codes = {}
        self.user_profiles = {}  # Initialize user profiles dictionary
        self.active_orders = {}  # Initialize active orders dictionary
        self.save_thread = threading.Thread(target=self.save_profiles_periodically)
        self.save_thread.daemon = True  # Daemonize the save thread
        self.load_profiles_from_txt()  # Load profiles when the ProfileManager is initialized
        self.save_thread.start()  # Start the save thread

    def save_profiles_periodically(self, interval=1):
        while True:
            self.save_profiles()
            time.sleep(interval)


    def load_profiles_from_txt(self, filename='user_profiles.txt'):
        try:
            with open(filename, 'r') as file:
                for line in file:
                    chat_id, name, credits = line.strip().split(',')
                    self.user_profiles[int(chat_id)] = {
                        'name': name,
                        'credits': int(credits)
                    }
        except FileNotFoundError:
            pass

    def save_profiles(self, filename='user_profiles.txt'):
        # Make a copy of the user profiles dictionary
        profiles_copy = self.user_profiles.copy()
        with open(filename, 'w') as file:
            for chat_id, profile in profiles_copy.items():
                # Convert credits to integer explicitly
                credits = int(profile['credits'])
                file.write(f"{chat_id},{profile['name']},{credits}\n")


    def update_profile(self, chat_id, name=None, credits=None):
        if chat_id in self.user_profiles:
            if name is not None:
                self.user_profiles[chat_id]['name'] = name
            if credits is not None:
                self.user_profiles[chat_id]['credits'] = credits
            # Save the updated profile to the file immediately
            self.save_profiles()
            return True
        else:
            return False

    def get_user_profile(self, chat_id):
        return self.user_profiles.get(chat_id)
    
    def remove_credits(self, chat_id, credits):
        if chat_id in self.user_profiles:
            if self.user_profiles[chat_id]['credits'] >= credits:
                self.user_profiles[chat_id]['credits'] -= credits
                # Save the updated profile to the file immediately
                self.save_profiles()
                return True
            else:
                return False
        else:
            return False
    
    def request_sms(self, chat_id, order_id):
        threading.Thread(target=self.wait_for_sms_active_number, args=(chat_id, order_id)).start()

    def wait_for_sms_active_number(self, chat_id, order_id):
        start_time = time.time()
        while time.time() - start_time < 300:  # Wait for 5 minutes
            sms_messages = self.get_sms_messages(order_id)
            if sms_messages:
                for sms_message in sms_messages:
                    public_bot.send_message(chat_id, "Received Code: " + sms_message)
                break
            time.sleep(1)  # Check every 1 second
        self.active_orders.pop(chat_id, None)

    def create_profile(self, chat_id):
        if chat_id not in self.user_profiles:
            # Create a new profile only if the chat ID is not already in use
            self.user_profiles[chat_id] = {
                'chat_id': chat_id,
                'name': None,
                'credits': 0
            }
            # Save the updated profiles to the JSON file
            self.save_profiles()

    def get_user_profile(self, chat_id):
        return self.user_profiles.get(chat_id)

    def add_credits(self, chat_id, credits):
        if chat_id in self.user_profiles:
            self.user_profiles[chat_id]['credits'] += credits
            # Save the updated profile to the file immediately
            self.save_profiles()
            return True
        else:
            return False

    def redeem_credits(self, chat_id, credits):
        if chat_id in self.user_profiles:
            if self.user_profiles[chat_id]['credits'] >= credits:
                self.user_profiles[chat_id]['credits'] -= credits
                # Save the updated profile to the file immediately
                self.save_profiles()
                return True
            else:
                return False
        else:
            return False
  
    waiting_flag = True
    
    def wait_for_sms_active_number(self, chat_id, order_id):
        start_time = time.time()
        activation_in_progress = True
        while time.time() - start_time < 300 and activation_in_progress:  # Wait for 5 minutes or until activation is completed
            if not activation_in_progress:
                break  # Exit the loop if activation is canceled

            order_status = self.get_order_status(order_id)
            if order_status == "completed":
                print("Order has been completed. Exiting the loop.")
                activation_in_progress = False
                break

            sms_messages = self.get_sms_messages(order_id)
            if sms_messages:
                for sms_message in sms_messages:
                    public_bot.send_message(chat_id, f"Received Code: {sms_message}")
                # Display current credits
                user_profile = self.get_user_profile(chat_id)
                if user_profile:
                    credit_balance = user_profile['credits']
                    public_bot.send_message(chat_id, f"Your balance : {credit_balance} credits")
                else:
                    public_bot.send_message(chat_id, "Error: Unable to retrieve current credits")
                # Exit the loop
                activation_in_progress = False
                self.active_orders.pop(chat_id, None)  # Remove active order
                break

            if chat_id not in self.active_orders:
                activation_in_progress = False  # Exit the loop if order is canceled
                break

            time.sleep(1)  # Check every 1 second

        if activation_in_progress:
            # If activation is still in progress after timeout, refund credits and send message
            self.active_orders.pop(chat_id, None)  # Remove active order
            self.add_credits(chat_id, 10)  # Refund 10 credits
            public_bot.send_message(chat_id, "Activation timed out. Your credits have been refunded.")



    def get_order_status(self, order_id):
        headers = {
            'Authorization': 'Bearer ' + self.fivesim_token,
            'Accept': 'application/json',
        }
        response = requests.get(f'https://{self.domain}/v1/user/check/{order_id}', headers=headers)
        if response.status_code == 200:
            try:
                data = response.json()
                return data.get('status')
            except json.JSONDecodeError as e:
                print("JSON Decode Error:", e)
                print("Response Content:", response.content)
                return None
        else:
            print("Failed to fetch order status:", response.text)
            return None

    def get_sms_messages(self, order_id):
        headers = {
            'Authorization': 'Bearer ' + self.fivesim_token,
            'Accept': 'application/json',
        }
        response = requests.get(f'https://{self.domain}/v1/user/finish/{order_id}', headers=headers)
        if response.status_code == 200:
            try:
                data = response.json()
                sms_messages = []
                if 'sms' in data:
                    for sms in data['sms']:
                        sms_messages.append(sms['text'])
                return sms_messages
            except json.JSONDecodeError as e:
                print("JSON Decode Error:", e)
                print("Response Content:", response.content)
                return None
        else:
            print("Failed to fetch SMS messages:", response.text)
            return None

    def request_number(self, chat_id):
        if chat_id not in self.active_orders or not self.active_orders[chat_id]['activation_in_progress']:
            url = f'https://{self.domain}/v1/user/buy/activation/{self.country}/{self.operator}/{self.service}'
            headers = {
                'Authorization': f'Bearer {self.fivesim_token}',
                'Accept': 'application/json',
            }
            response = requests.get(url, headers=headers)
            try:
                data = response.json()
                if response.status_code == 200:
                    order_id = data.get('id')
                    phone_number = data.get('phone')
                    country = data.get('country')
                    self.active_orders[chat_id] = {'order_id': order_id, 'phone_number': phone_number,
                                                   'Country': country, 'activation_in_progress': True}
                    if chat_id in self.user_profiles:
                        if self.deduct_credits(chat_id, 10):  # Deduct 10 credits per active number
                            # Start waiting for SMS
                            threading.Thread(target=self.wait_for_sms_active_number, args=(chat_id, order_id)).start()
                            return order_id, phone_number, country, None  # Include country
                        else:
                            return None, None, None, "Insufficient credits"
                    else:
                        return None, None, None, "User profile not found"
                elif response.status_code == 400 and data.get('message') == 'no free phones':
                    return None, None, None, "The server is busy now. Please try again 10 minutes later."
                else:
                    return None, None, None, f"The server is busy now. Please try again 10 minutes later."
            except json.JSONDecodeError as e:
                print("JSON Decode Error:", e)
                print("Response Content:", response.content)
                return None, None, None, "Failed to decode JSON response"
            except Exception as e:
                print("Error:", e)
                return None, None, None, f"Error occurred: {e}"
        else:
            return None, None, None, "The server is busy now. Please try again 10 minutes later."

    def cancel_activation(self, chat_id):
        if chat_id in self.active_orders:
            order_id = self.active_orders[chat_id]['order_id']
            url = f'https://{self.domain}/v1/user/cancel/{order_id}'
            headers = {
                'Authorization': f'Bearer {self.fivesim_token}',
                'Accept': 'application/json',
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                refunded_credits = 10  # Assuming 10 credits are refunded per canceled order
                self.add_credits(chat_id, refunded_credits)  # Refund credits
                self.active_orders.pop(chat_id)
                public_bot.send_message(chat_id, "Number activation canceled successfully. Your credits have been refunded.")
                # Set activation_in_progress to False
                self.active_orders[chat_id]['activation_in_progress'] = False
                return True, None
            else:
                return False, "Failed to cancel number activation."
        else:
            return False, "No active numbers to cancel."

    def generate_redeem_code(self, credits):
        code = ''.join(random.choices(string.digits, k=8))
        while code in self.redeem_codes:
            code = ''.join(random.choices(string.digits, k=8))
        self.redeem_codes[code] = credits
        return code

    def redeem_code(self, redeem_code):
        if redeem_code in self.redeem_codes:
            credits = self.redeem_codes.pop(redeem_code)
            return credits
        else:
            return None

    def deduct_credits(self, chat_id, credits):
        if chat_id in self.user_profiles:
            if self.user_profiles[chat_id]['credits'] >= credits:
                self.user_profiles[chat_id]['credits'] -= credits
                return True
            else:
                return False
        else:
            return False

class ChatIDManager:
    def __init__(self, file_path="approval.txt"):
        self.allowed_chat_ids = set()
        self.file_path = file_path
        self.load_approved_chat_ids()

    def load_approved_chat_ids(self):
        try:
            with open(self.file_path, 'r') as file:
                lines = file.readlines()
                self.allowed_chat_ids = set(line.strip() for line in lines)
        except FileNotFoundError:
            pass

    def save_approved_chat_ids(self):
        with open(self.file_path, 'w') as file:
            for chat_id in self.allowed_chat_ids:
                file.write(f"{chat_id}\n")

    def add_chat_id(self, chat_id):
        if str(chat_id) not in self.allowed_chat_ids:
            self.allowed_chat_ids.add(str(chat_id))
            self.save_approved_chat_ids()
            
            # Send a message to the newly approved chat ID
            public_bot.send_message(chat_id, "You have been approved to use the bot. Welcome! Send Agian /Start")
            
            return True
        else:
            return False

    def remove_chat_id(self, chat_id):
        self.allowed_chat_ids.discard(str(chat_id))
        self.save_approved_chat_ids()

    def is_chat_id_allowed(self, chat_id):
        return str(chat_id) in self.allowed_chat_ids

# Define your Telegram bot tokens
public_bot_token = '6698942063:AAGr7_MjL60e9aMLVrJ0hcknPz-FcyGSm3s'
admin_bot_token = '6991322475:AAGzaI4im8oVXORYOPliaQBRRdC4zh_0eOk'

# Admin chat ID
ADMIN_CHAT_ID = '939525915'

# Create bot instances
public_bot = telebot.TeleBot(public_bot_token)
admin_bot = telebot.TeleBot(admin_bot_token)

# Create a ProfileManager instance
fivesim_token = 'eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDEzNDE0MDgsImlhdCI6MTcwOTgwNTQwOCwicmF5IjoiZTYzZWE1MzMyN2VmYTg2ZTEyNjAxMzNkOTQ2NWIyYWIiLCJzdWIiOjEwMDU4ODR9.ZFca9hzfVO-RzfXOlxpUZyi_kG9PugoypaSSOML2ibR-G2X25GQ0cTlirOVca0VK3cOyoFrc0uQc9yHZxWVFSTGagPBJF1E5t4HCj4BzFt1mPZwJt7YiLrEyXu3g1JxgJogQxy0xFXt5JxrHKhO3PumpFqBqU32NE2s7JD36gkNJgmM2lhRg-i28CgCmENEg1BJki4isQ_PadUFZOWjADiEMOaNWXJXnGoPQpz10tuxf3JP9dBokeyzkRgh4U0hkzwksAZm2GD30L51ux-2eyJ3AT6vzdmzLJjzF4hxU2KWnF1Ws6YtYM29w4Ofx_OCMnS8_PpAs0vJKvfGLlsV6Sw'
country = 'indonesia'
service = 'facebook'
operator = 'virtual38'
domain = '5sim.net'
profile_manager = ProfileManager(fivesim_token, country, service, operator, domain)

# Create a ChatIDManager instance
chat_id_manager = ChatIDManager()

# Handler for the /profile command
@public_bot.message_handler(commands=['profile'])
def show_profile(message):
    chat_id = message.chat.id
    if chat_id_manager.is_chat_id_allowed(chat_id):
        user_profile = profile_manager.get_user_profile(chat_id)
        if user_profile:
            user_name = message.from_user.first_name
            credit_balance = user_profile['credits']
            profile_text = f"Name: {user_name}\nChat ID: {chat_id}\nCredit Balance: {credit_balance} credits"
            public_bot.send_message(chat_id, profile_text)
        else:
            public_bot.send_message(chat_id, "Your profile information is not available.")
    else:
        public_bot.send_message(chat_id, "You are not authorized to use this bot.")

@public_bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    if chat_id_manager.is_chat_id_allowed(chat_id):
        user_profile = profile_manager.get_user_profile(chat_id)
        if user_profile:
            profile_message = "Your profile already exists. You can use the bot's functionalities."
            public_bot.send_message(chat_id, profile_message)
        else:
            if os.path.isfile('user_profiles.txt'):
                # Check if the profile exists for the given chat_id in the loaded profiles
                profile_manager.load_profiles_from_txt()
                user_profile = profile_manager.get_user_profile(chat_id)
                if user_profile:
                    profile_message = "Your old profile has been restored. You can use the bot's functionalities."
                    public_bot.send_message(chat_id, profile_message)
                else:
                    profile_manager.create_profile(chat_id)
                    welcome_message = f"Welcome! Your profile has been created. Your Chat ID is: {chat_id}"
                    public_bot.send_message(chat_id, welcome_message)
            else:
                profile_manager.create_profile(chat_id)
                welcome_message = f"Welcome! Your profile has been created. Your Chat ID is: {chat_id}"
                public_bot.send_message(chat_id, welcome_message)
    else:
        not_authorized_message = f"You are not authorized to use this bot. Your Chat ID is: {chat_id} admin @mdsuhailrana"
        public_bot.send_message(chat_id, not_authorized_message)



# Handler for /get_number command for public bot
@public_bot.message_handler(commands=['number'])
def get_number(message):
    chat_id = message.chat.id
    if chat_id_manager.is_chat_id_allowed(chat_id):
        user_profile = profile_manager.get_user_profile(chat_id)
        if user_profile and user_profile['credits'] >= 10:  # Check if user has enough credits
            if chat_id not in profile_manager.active_orders or not profile_manager.active_orders[chat_id]['activation_in_progress']:
                order_id, phone_number, country, error = profile_manager.request_number(chat_id)  # Include country
                if order_id:
                    response = f"New Phone Number: {phone_number}\nCountry : {country}\nOrder ID: {order_id}"  # Include country
                    keyboard = InlineKeyboardMarkup()
                    get_sms_button = InlineKeyboardButton("Get SMS", callback_data='get_sms')
                    cancel_button = InlineKeyboardButton("Cancel Activation", callback_data='cancel')
                    keyboard.add(get_sms_button, cancel_button)
                    public_bot.send_message(chat_id, response, reply_markup=keyboard)
                    # Send message indicating waiting for SMS here
                else:
                    public_bot.send_message(chat_id, f"The server is busy now. Please try again 10 minutes later.")
            else:
                public_bot.send_message(chat_id, "Phone number activation is already in progress. Please wait.")
        else:
            public_bot.send_message(chat_id, "You do not have enough credits Pleass Add credits admin @mdsuhailrana.")
    else:
        public_bot.send_message(chat_id, "You are not authorized to use this bot.")


# Define a flag to indicate if waiting should continue
waiting_flag = True

# Function to handle getting SMS messages
def handle_get_sms(call):
    global waiting_flag
    chat_id = call.message.chat.id
    if chat_id in profile_manager.active_orders:
        public_bot.send_message(chat_id, "Waiting for SMS.. Please wait 1/2 Minutes.")
        for _ in range(30):  # Check every 10 seconds for 5 minutes
            time.sleep(10)  # Wait for 10 seconds
            if not waiting_flag or not profile_manager.active_orders[chat_id]['activation_in_progress']:
                break  # Exit the loop if waiting is canceled or activation is no longer in progress

        if waiting_flag:
            order_id = profile_manager.active_orders[chat_id]['order_id']
            sms_messages = profile_manager.get_sms_messages(order_id)  # Correct method name here
            if sms_messages:
                for sms_message in sms_messages:
                    public_bot.send_message(chat_id, f"Received Code: {sms_message}")
                # Deduct 10 credits for receiving SMS
                if profile_manager.deduct_credits(chat_id, 10):
                    public_bot.send_message(chat_id, "You have been charged 10 credits for receiving SMS.")
                else:
                    public_bot.send_message(chat_id, "Insufficient credits. Please recharge to continue.")
            else:
                # Close waiting period
                waiting_flag = False
                public_bot.send_message(chat_id, "No SMS received. Your credits will be refunded.")
                # Refund 10 credits for waiting 5 minutes without SMS
                profile_manager.add_credits(chat_id, 10)
                profile_manager.active_orders.pop(chat_id)  # Remove current active order

        if not waiting_flag:
            # Refund 10 credits for waiting 5 minutes without SMS
            profile_manager.add_credits(chat_id, 10)
            profile_manager.active_orders.pop(chat_id)  # Remove current active order
            public_bot.send_message(chat_id, "Waiting period has ended. Your credits have been refunded.")


# Function to handle cancel operation
def handle_cancel(call):
    global waiting_flag
    waiting_flag = False

# Handler for callback queries (button clicks) for public bot
@public_bot.callback_query_handler(func=lambda call: call.data in ['cancel', 'get_sms'])
def handle_callback_query(call):
    chat_id = call.message.chat.id
    try:
        if call.message.date + 300 > time.time():  # Check if the callback query is still valid (within 5 minutes)
            if call.data == 'cancel':
                success, error_message = profile_manager.cancel_activation(chat_id)
                if success:
                    public_bot.answer_callback_query(call.id, "Number activation canceled successfully!")
                    waiting_flag = False  # Set waiting_flag to False
                    handle_cancel(call)  # Call the function to handle cancellation
                else:
                    public_bot.answer_callback_query(call.id, f"Failed to cancel number activation: {error_message}")
            elif call.data == 'get_sms':
                handle_get_sms(call)
        else:
            public_bot.answer_callback_query(call.id, "Callback query expired. Please try again.")
    except Exception as e:
        print(f"Error handling callback query: {e}")

# Handler for redeeming codes
@public_bot.message_handler(commands=['redeem'])
def redeem_code(message):
    chat_id = message.chat.id
    if chat_id_manager.is_chat_id_allowed(chat_id):
        try:
            code = message.text.split()[1]  # Assuming the command format is "/redeem <code>"
            credits = profile_manager.redeem_code(code)

            if credits is not None:
                profile_manager.add_credits(chat_id, credits)
                public_bot.send_message(chat_id, f"You've redeemed {credits} credits!")
            else:
                public_bot.send_message(chat_id, "Invalid or expired code.")
        except IndexError:
            public_bot.send_message(chat_id, "Please provide the redemption code in the format '/redeem <code>'.")
    else:
        public_bot.send_message(chat_id, "You are not authorized to use this bot.")


# Handler for adding users to the approval list
@admin_bot.message_handler(commands=['add'])
def add_approval(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        if len(message.text.split()) == 2:
            new_chat_id = message.text.split()[1]
            chat_id_manager.add_chat_id(new_chat_id)
            admin_bot.reply_to(message, f"User with ID {new_chat_id} added to the approval list.")
        else:
            admin_bot.reply_to(message, "Invalid command format. Usage: /add <chat_id>")
    else:
        admin_bot.reply_to(message, "Access denied. You are not authorized to use this command.")

# Handler for removing users from the approval list
@admin_bot.message_handler(commands=['remove'])
def remove_approval(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        if len(message.text.split()) == 2:
            remove_chat_id = message.text.split()[1]
            chat_id_manager.remove_chat_id(remove_chat_id)
            admin_bot.reply_to(message, f"User with ID {remove_chat_id} removed from the approval list.")
        else:
            admin_bot.reply_to(message, "Invalid command format. Usage: /remove <chat_id>")
    else:
        admin_bot.reply_to(message, "Access denied. You are not authorized to use this command.")

# Handler for generating redeem codes command for admin bot
@admin_bot.message_handler(commands=['code'])
def generate_redeem_code(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        parameters = message.text.split()
        if len(parameters) == 2:
            credits = int(parameters[1])
            code = profile_manager.generate_redeem_code(credits)
            admin_bot.send_message(chat_id, f"Your redeem code: {code} for {credits} credits.")
        else:
            admin_bot.send_message(chat_id, "Invalid command format. Usage: /code <credits>")
    else:
        admin_bot.send_message(chat_id, "Access denied. You are not authorized to use this command.")


# Handler for the help command for admin bot
@admin_bot.message_handler(commands=['help'])
def admin_help(message):
    chat_id = message.chat.id
    help_message = """Admin Bot Help:
    /add <chat_id>: Add a user to the approval list
    /remove <chat_id>: Remove a user from the approval list
    /code <credits>: Generate a redeem code with specified credits
    /post <massage>: Send massage to all user
    /profile <chat_id>: For show user profile info
    /country <country>: For Chnage New country
    /operator <operator>: For Chnage operator
    /remove_credits <user_chat_id> <amount>: For user credit remove
    """
    admin_bot.send_message(chat_id, help_message)

# Handler for the help command for public bot
@public_bot.message_handler(commands=['help'])
def public_help(message):
    chat_id = message.chat.id
    help_message = """Public Bot Help:
    /start: Create your profile
    /profile: View your profile information
    /number: Get a new phone number for verification
    /redeem <code>: Redeem a code for credits
    Contact admin: @mdsuhailrana
    """
    public_bot.send_message(chat_id, help_message)

# Disable Pylance warning for unused variable
@public_bot.message_handler(func=lambda message: True)  # pylint: disable=unused-argument
def echo_all(message):
    public_bot.reply_to(message, "I don't understand your message.")

@admin_bot.message_handler(commands=['post'])
def post_message(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        try:
            # Extract the message content after the command
            message_content = message.text.split('/post', 1)[1].strip()
            
            # Iterate over all approved chat IDs
            for approved_chat_id in chat_id_manager.allowed_chat_ids:
                try:
                    # Send the message using the public bot
                    public_bot.send_message(approved_chat_id, message_content)
                    print(f"Message sent to {approved_chat_id}")
                except Exception as e:
                    # Handle exceptions (e.g., invalid chat IDs)
                    print(f"Error sending message to {approved_chat_id}: {e}")
            
            admin_bot.send_message(chat_id, "Message sent to all approved users.")
        except Exception as e:
            print(f"Error: {e}")
            admin_bot.send_message(chat_id, f"Error: {e}")
    else:
        admin_bot.send_message(chat_id, "Access denied. You are not authorized to use this command.")


# Handler for the /profile command for admin bot
@admin_bot.message_handler(commands=['profile'])
def show_profile(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        try:
            # Extract the chat ID of the user whose profile is requested
            requested_chat_id = int(message.text.split()[1])
            user_profile = profile_manager.get_user_profile(requested_chat_id)
            if user_profile:
                user_name = user_profile.get('name', 'Unknown')
                credit_balance = user_profile['credits']
                profile_text = f"Name: {user_name}\nChat ID: {requested_chat_id}\nCredit Balance: {credit_balance} credits"
                admin_bot.send_message(chat_id, profile_text)
            else:
                admin_bot.send_message(chat_id, "User profile not found.")
        except IndexError:
            admin_bot.send_message(chat_id, "Please provide the chat ID of the user.")
        except ValueError:
            admin_bot.send_message(chat_id, "Invalid chat ID.")
    else:
        admin_bot.send_message(chat_id, "Access denied. You are not authorized to use this command.")


# Handler for changing the country
@admin_bot.message_handler(commands=['country'])
def set_country(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        try:
            new_country = message.text.split()[1]
            profile_manager.country = new_country
            admin_bot.send_message(chat_id, f"Country has been set to: {new_country}")
        except IndexError:
            admin_bot.send_message(chat_id, "Invalid command format. Usage: /country <country>.")
    else:
        admin_bot.send_message(chat_id, "Access denied. You are not authorized to use this command.")

# Handler for changing the operator
@admin_bot.message_handler(commands=['operator'])
def set_operator(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        try:
            new_operator = message.text.split()[1]
            profile_manager.operator = new_operator
            admin_bot.send_message(chat_id, f"Operator has been set to: {new_operator}")
        except IndexError:
            admin_bot.send_message(chat_id, "Invalid command format. Usage: /operator <operator>.")
    else:
        admin_bot.send_message(chat_id, "Access denied. You are not authorized to use this command.")

# Handler for the /remove_credits command for admin bot
@admin_bot.message_handler(commands=['remove_credits'])
def remove_credits_admin(message):
    chat_id = message.chat.id
    if message.from_user.id == int(ADMIN_CHAT_ID):
        try:
            parameters = message.text.split()
            if len(parameters) == 3:
                target_chat_id = int(parameters[1])
                amount = int(parameters[2])
                if amount > 0:
                    if profile_manager.remove_credits(target_chat_id, amount):
                        admin_bot.send_message(chat_id, f"{amount} credits have been removed from user {target_chat_id}.")
                    else:
                        admin_bot.send_message(chat_id, "User has insufficient credits.")
                else:
                    admin_bot.send_message(chat_id, "Invalid amount. Please provide a positive number.")
            else:
                admin_bot.send_message(chat_id, "Invalid command format. Usage: /remove_credits <user_chat_id> <amount>")
        except ValueError:
            admin_bot.send_message(chat_id, "Invalid chat ID or amount. Please provide valid numbers.")
    else:
        admin_bot.send_message(chat_id, "Access denied. You are not authorized to use this command.")


# Start polling for both bots in separate threads
public_bot_thread = threading.Thread(target=public_bot.polling)
public_bot_thread.start()

admin_bot_thread = threading.Thread(target=admin_bot.polling)
admin_bot_thread.start()
