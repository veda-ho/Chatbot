const sendButton = document.getElementById("send-button");
const userInput = document.getElementById("user-input");
const chatBox = document.getElementById("chat-box");


function sendMessage() {

    const message = userInput.value.trim();

    // Don't send an empty message
    if (message === "") {
        return;
    }

    // Create a new message bubble
    const messageElement = document.createElement("div");

    messageElement.classList.add("message", "user-message");
    messageElement.textContent = message;

    // Add it to the chat
    chatBox.appendChild(messageElement);

    // Clear the textbox
    userInput.value = "";

    // Scroll to newest message
    chatBox.scrollTop = chatBox.scrollHeight;
}


// Send when button is clicked
sendButton.addEventListener("click", sendMessage);


// Also send when Enter is pressed
userInput.addEventListener("keypress", function(event) {

    if (event.key === "Enter") {
        sendMessage();
    }

});