with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# Add comments for MessageItem
content = content.replace("const MessageItem = memo(({ msg, onSendMessage, onDownload }: MessageItemProps) => {",
"""// ⚡ Bolt: Wraps the message item in React.memo to prevent unnecessary re-renders.
// Since the 'input' state is stored in the parent (Home) and updates on every keystroke,
// this optimization ensures that the entire chat history isn't re-rendered on every key press,
// saving CPU cycles and reducing input latency, especially in long conversations.
const MessageItem = memo(({ msg, onSendMessage, onDownload }: MessageItemProps) => {""")

# Add comments for useCallback
content = content.replace("const sendMessage = useCallback(async (userMessage: string) => {",
"""  // ⚡ Bolt: Wraps handlers in useCallback so their memory references remain stable.
  // If these were re-created on every render, React.memo on MessageItem would be defeated
  // since it would see "new" prop references and re-render anyway.
  const sendMessage = useCallback(async (userMessage: string) => {""")

with open("frontend/src/app/page.tsx", "w") as f:
    f.write(content)
