const sendButton =
    document.getElementById("send-button");

const userInput =
    document.getElementById("user-input");

const chatBox =
    document.getElementById("chat-box");

const userType =
    document.getElementById("user-type");

const micButton =
    document.getElementById("mic-button");


// What the bot remembers from earlier messages
// (university, city, date, school, cGPA...), sent back each time
let context = {};


// ========================================
// SEND MESSAGE
// ========================================

async function sendMessage() {

    const message =
        userInput.value.trim();


    if (message === "") {
        return;
    }


    // ------------------------------------
    // Display user's message
    // ------------------------------------

    const userMessage =
        document.createElement("div");

    userMessage.classList.add(
        "message",
        "user-message"
    );

    userMessage.textContent = message;

    chatBox.appendChild(userMessage);


    // Clear input box
    userInput.value = "";


    // Scroll down
    chatBox.scrollTop =
        chatBox.scrollHeight;


    // ------------------------------------
    // Show temporary loading message
    // ------------------------------------

    const loadingMessage =
        document.createElement("div");

    loadingMessage.classList.add(
        "message",
        "bot-message"
    );

    loadingMessage.textContent =
        "Thinking...";

    chatBox.appendChild(
        loadingMessage
    );


    chatBox.scrollTop =
        chatBox.scrollHeight;


    // ------------------------------------
    // Send message to Flask
    // ------------------------------------

    try {

        const response = await fetch(
            "/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: message,
                    user_type: userType.value,
                    context: context
                })
            }
        );


        const data =
            await response.json();


        // Remember details for the next question
        if (data.context) {
            context = data.context;
        }


        // Remove "Thinking..."
        loadingMessage.remove();


        // Display chatbot reply
        addBotMessage(
            data.reply
        );

    }

    catch (error) {

        console.error(
            "Chat error:",
            error
        );


        loadingMessage.remove();


        addBotMessage(
            "Sorry, something went wrong."
        );

    }
}


// ========================================
// ADD BOT MESSAGE
// ========================================

function addBotMessage(text) {

    const botMessage =
        document.createElement("div");

    botMessage.classList.add(
        "message",
        "bot-message"
    );

    botMessage.textContent =
        text;

    chatBox.appendChild(
        botMessage
    );


    chatBox.scrollTop =
        chatBox.scrollHeight;
}


// ========================================
// SEND BUTTON
// ========================================

sendButton.addEventListener(
    "click",
    sendMessage
);


// ========================================
// ENTER KEY
// ========================================

userInput.addEventListener(
    "keypress",
    function(event) {

        if (event.key === "Enter") {

            sendMessage();

        }

    }
);


// ========================================
// MIC BUTTON (SPEECH TO TEXT)
// Uses the browser's built-in speech recognition (Chrome / Edge)
// ========================================

const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;


if (SpeechRecognition) {

    const recognition =
        new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.interimResults = false;


    micButton.addEventListener(
        "click",
        function() {

            micButton.classList.add("listening");
            recognition.start();

        }
    );


    // Put what the user said into the box, then send it
    recognition.addEventListener(
        "result",
        function(event) {

            userInput.value =
                event.results[0][0].transcript;

            sendMessage();

        }
    );


    recognition.addEventListener(
        "end",
        function() {

            micButton.classList.remove("listening");

        }
    );


    recognition.addEventListener(
        "error",
        function(event) {

            console.error("Speech error:", event.error);
            micButton.classList.remove("listening");

        }
    );

}

else {

    micButton.title =
        "Voice input works in Chrome or Edge";

    micButton.addEventListener(
        "click",
        function() {

            addBotMessage(
                "Voice input isn't supported in this browser. Try Chrome or Edge."
            );

        }
    );

}
