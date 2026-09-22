const sendButton =
    document.getElementById("send-button");

const userInput =
    document.getElementById("user-input");

const chatBox =
    document.getElementById("chat-box");


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
                    message: message
                })
            }
        );


        const data =
            await response.json();


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