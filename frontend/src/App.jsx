import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://localhost:8000/api';
const WS_BASE = 'ws://localhost:8000/ws/chat/';
const API_KEY = 'default-key-change-this'; // Matching backend default. In production, use env vars.

const fetchWithAuth = (url, options = {}) => {
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'X-API-KEY': API_KEY
    }
  });
};

const Avatar = ({ name, color, size = 40 }) => (
  <div className="avatar" style={{ backgroundColor: color || '#075e54', width: size, height: size }}>
    {name ? name[0].toUpperCase() : '?'}
  </div>
);

function App() {
  const [activePlatform, setActivePlatform] = useState('whatsapp');
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);
  const [sidebarTab, setSidebarTab] = useState('chats');
  const [inputText, setInputText] = useState('');
  const [subject, setSubject] = useState('');
  const [mediaUrl, setMediaUrl] = useState(null);
  const [replyingTo, setReplyingTo] = useState(null);
  const [isComposing, setIsComposing] = useState(false);
  const [newRecipient, setNewRecipient] = useState('');
  const [selectedRecipients, setSelectedRecipients] = useState([]);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showContactDropdown, setShowContactDropdown] = useState(false);
  const [waProvider, setWaProvider] = useState('twilio');
  
  const messagesEndRef = useRef(null);
  const ws = useRef(null);
  
  const activePlatformRef = useRef(activePlatform);
  const selectedContactRef = useRef(selectedContact);

  useEffect(() => { activePlatformRef.current = activePlatform; }, [activePlatform]);
  useEffect(() => { selectedContactRef.current = selectedContact; }, [selectedContact]);

  useEffect(() => {
    fetchConversations();
    fetchContacts();
    setupWebSocket();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  useEffect(() => {
    setSelectedContact(null);
    setIsComposing(false);
    setReplyingTo(null);
    setMediaUrl(null);
    setShowAttachMenu(false);
    setSelectedRecipients([]);
  }, [activePlatform]);

  useEffect(() => {
    if (selectedContact) {
      fetchMessages(selectedContact.contact_identifier);
      markAsRead(selectedContact.contact_identifier);
      setReplyingTo(null);
      setMediaUrl(null);
      setIsComposing(false);
    }
  }, [selectedContact]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isComposing]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchConversations = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/conversations/`);
      const data = await res.json();
      setConversations(data);
    } catch (err) {
      console.error("Failed to fetch conversations", err);
    }
  };

  const fetchContacts = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/contacts/`);
      const data = await res.json();
      setContacts(data);
    } catch (err) {
      console.error("Failed to fetch contacts", err);
    }
  };

  const fetchMessages = async (identifier) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/messages/?contact_identifier=${identifier}&channel=${activePlatformRef.current}`);
      const data = await res.json();
      setMessages(data);
    } catch (err) {
      console.error("Failed to fetch messages", err);
    }
  };

  const markAsRead = async (identifier) => {
    try {
      await fetchWithAuth(`${API_BASE}/messages/mark_read/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contact_identifier: identifier })
      });
      fetchConversations();
    } catch (err) {
      console.error("Failed to mark read", err);
    }
  };

  const toggleStar = async (msgId) => {
    try {
      await fetchWithAuth(`${API_BASE}/messages/toggle_star/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: msgId })
      });
      if (selectedContactRef.current) fetchMessages(selectedContactRef.current.contact_identifier);
    } catch (err) {
      console.error("Failed to toggle star", err);
    }
  };

  const setupWebSocket = () => {
    ws.current = new WebSocket(WS_BASE);
    ws.current.onmessage = (e) => {
      const newMsg = JSON.parse(e.data);
      const currentContact = selectedContactRef.current;
      const currentPlatform = activePlatformRef.current;

      if (currentContact && newMsg.contact_identifier === currentContact.contact_identifier && newMsg.channel === currentPlatform) {
        setMessages(prev => [...prev, newMsg]);
        markAsRead(currentContact.contact_identifier);
      }
      fetchConversations();
    };

    ws.current.onclose = () => {
      console.log("WebSocket closed. Reconnecting in 3s...");
      setTimeout(setupWebSocket, 3000); // FIX: Reconnect logic
    };
  };

  const sendMessage = async () => {
    let recipients = [...selectedRecipients];
    if (newRecipient.trim()) recipients.push(newRecipient.trim());
    const toStr = recipients.join(', ') || selectedContact?.contact_identifier;
    const channel = activePlatform;

    if (!toStr || (!inputText && !mediaUrl)) return;

    const payload = {
      channel,
      to: toStr,
      body: inputText,
      subject: channel === 'email' ? (subject || selectedContact?.subject || 'No Subject') : null,
      media_url: mediaUrl,
      reply_to: replyingTo?.id,
      thread_id: selectedContact?.thread_id,
      provider: channel === 'whatsapp' ? waProvider : undefined
    };

    try {
      const res = await fetchWithAuth(`${API_BASE}/messages/send/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        setInputText('');
        setSubject('');
        setMediaUrl(null);
        setReplyingTo(null);
        setIsComposing(false);
        setNewRecipient('');
        setSelectedRecipients([]);
        setShowAttachMenu(false);
        fetchConversations();
        fetchContacts();
        
        if (!Array.isArray(data) && isComposing) {
           setSelectedContact(data);
        } else if (!isComposing && selectedContact) {
           fetchMessages(selectedContact.contact_identifier);
        }
      } else {
        const errData = await res.json();
        alert(errData.error || "Failed to send message");
      }
    } catch (err) {
      console.error("Failed to send message", err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetchWithAuth(`${API_BASE}/upload/`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      setMediaUrl(data.url);
      if (activePlatform === 'email') setSubject(`📎 Attached: ${file.name}`);
      setShowAttachMenu(false);
    } catch (err) {
      console.error("Upload failed", err);
    }
  };

  const addRecipient = (identifier) => {
    if (!selectedRecipients.includes(identifier)) {
      setSelectedRecipients([...selectedRecipients, identifier]);
    }
    setNewRecipient('');
    setShowContactDropdown(false);
  };

  const removeRecipient = (identifier) => {
    setSelectedRecipients(selectedRecipients.filter(r => r !== identifier));
  };

  const startChatFromContact = (contact) => {
    const existingConv = conversations.find(c => c.contact_identifier === contact.identifier && c.channel === activePlatform);
    if (existingConv) {
      setSelectedContact(existingConv);
    } else {
      setIsComposing(true);
      setSelectedRecipients([contact.identifier]);
      setSelectedContact(null);
    }
  };

  const filteredConversations = conversations.filter(c => c.channel === activePlatform);
  const filteredContacts = contacts.filter(c => c.channel === activePlatform);
  const matchedDropdownContacts = filteredContacts.filter(c => 
    !selectedRecipients.includes(c.identifier) &&
    (c.name.toLowerCase().includes(newRecipient.toLowerCase()) || 
     c.identifier.includes(newRecipient))
  );

  const getTicks = (status) => {
    if (!status) return <span style={{color: '#999'}}>✓</span>;
    if (status === 'read') return <span style={{color: '#34b7f1'}}>✓✓</span>;
    if (status === 'delivered') return <span style={{color: '#999'}}>✓✓</span>;
    return <span style={{color: '#999'}}>✓</span>;
  };

  return (
    <div className={`app-container theme-${activePlatform}`}>
      <div className="platform-rail">
        <div className={`rail-icon whatsapp ${activePlatform === 'whatsapp' ? 'active' : ''}`} onClick={() => setActivePlatform('whatsapp')} title="WhatsApp">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.414 0 .004 5.408 0 12.044c0 2.123.547 4.197 1.591 6.069L0 24l6.105-1.595a11.826 11.826 0 005.937 1.598h.005c6.637 0 12.05-5.408 12.056-12.044a11.833 11.833 0 00-3.417-8.485"/></svg>
        </div>
        <div className={`rail-icon email ${activePlatform === 'email' ? 'active' : ''}`} onClick={() => setActivePlatform('email')} title="Gmail">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
        </div>
      </div>

      <div className="sidebar">
        <div className="sidebar-header">
           <h2 style={{margin: '0 0 15px 0', fontSize: '20px'}}>{activePlatform === 'whatsapp' ? 'WhatsApp' : 'Gmail'}</h2>
           <button className="compose-btn" onClick={() => { setIsComposing(true); setSelectedContact(null); }}>
              <span>✎</span> Start New {activePlatform === 'whatsapp' ? 'Chat' : 'Email'}
           </button>
           <div className="sidebar-tabs">
              <button className={sidebarTab === 'chats' ? 'active' : ''} onClick={() => setSidebarTab('chats')}>Recent</button>
              <button className={sidebarTab === 'contacts' ? 'active' : ''} onClick={() => setSidebarTab('contacts')}>Contacts</button>
           </div>
           {activePlatform === 'whatsapp' && (
             <div style={{display: 'flex', gap: '6px', marginTop: '10px'}}>
               <button onClick={() => setWaProvider('twilio')} style={{flex: 1, padding: '5px', borderRadius: '12px', border: 'none', cursor: 'pointer', fontSize: '12px', background: waProvider === 'twilio' ? '#00a884' : '#e0e0e0', color: waProvider === 'twilio' ? 'white' : '#555'}}>Twilio</button>
               <button onClick={() => setWaProvider('cloud')} style={{flex: 1, padding: '5px', borderRadius: '12px', border: 'none', cursor: 'pointer', fontSize: '12px', background: waProvider === 'cloud' ? '#00a884' : '#e0e0e0', color: waProvider === 'cloud' ? 'white' : '#555'}}>Cloud API</button>
             </div>
           )}
        </div>
        
        <div className="inbox-list">
          {sidebarTab === 'chats' ? (
            filteredConversations.length > 0 ? (
              filteredConversations.map(conv => (
                <div key={`${conv.channel}-${conv.contact_identifier}`} className={`inbox-item ${selectedContact?.contact_identifier === conv.contact_identifier && selectedContact?.channel === conv.channel ? 'active' : ''}`} onClick={() => setSelectedContact(conv)}>
                  <Avatar name={conv.contact_name || conv.contact_identifier} color={activePlatform === 'whatsapp' ? '#25d366' : '#ea4335'} size={48} />
                  <div style={{flex: 1, minWidth: 0}}>
                    <div style={{display: 'flex', justifyContent: 'space-between'}}>
                      <span className="name">{conv.contact_name || conv.contact_identifier}</span>
                      <span style={{fontSize: '11px', color: '#999'}}>{conv.timestamp ? new Date(conv.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}</span>
                    </div>
                    <div className="last-msg">{conv.media_url ? '📷 Photo' : conv.body}</div>
                  </div>
                  {conv.unread_count > 0 && <div className="unread-badge">{conv.unread_count}</div>}
                </div>
              ))
            ) : <div style={{padding: '40px', textAlign: 'center', opacity: 0.5}}>No recent chats</div>
          ) : (
            filteredContacts.length > 0 ? (
              filteredContacts.map(contact => (
                <div key={contact.id} className="inbox-item" onClick={() => startChatFromContact(contact)}>
                  <Avatar name={contact.name} color={activePlatform === 'whatsapp' ? '#25d366' : '#ea4335'} size={48} />
                  <div style={{flex: 1}}>
                    <div className="name">{contact.name}</div>
                    <div style={{fontSize: '12px', color: '#999'}}>{contact.identifier}</div>
                  </div>
                </div>
              ))
            ) : <div style={{padding: '40px', textAlign: 'center', opacity: 0.5}}>No contacts found</div>
          )}
        </div>
      </div>

      <div className="chat-pane">
        {isComposing ? (
          <div style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
             <div className="chat-header" style={{background: activePlatform === 'whatsapp' ? '#075e54' : '#f1f3f4', color: activePlatform === 'whatsapp' ? 'white' : 'black'}}>
                <div style={{fontWeight: 'bold'}}>
                   {selectedRecipients.length > 1 ? `Broadcast to ${selectedRecipients.length} people` : 'New Message'}
                </div>
                <div style={{marginLeft: 'auto', cursor: 'pointer'}} onClick={() => setIsComposing(false)}>✕</div>
             </div>
             <div style={{padding: '30px', flex: 1, background: activePlatform === 'whatsapp' ? '#e5ddd5' : 'white'}}>
                <div style={{background: 'white', padding: '25px', borderRadius: '12px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', maxWidth: '600px', margin: '0 auto'}}>
                   <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px', borderBottom: '2px solid #eee', paddingBottom: '8px', marginBottom: '15px'}}>
                      {selectedRecipients.map(r => (
                        <div key={r} style={{background: activePlatform === 'whatsapp' ? '#dcf8c6' : '#e8f0fe', padding: '4px 12px', borderRadius: '16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px'}}>
                           {r} <span style={{cursor: 'pointer', fontWeight: 'bold'}} onClick={() => removeRecipient(r)}>×</span>
                        </div>
                      ))}
                      <input 
                        placeholder={selectedRecipients.length === 0 ? "Enter recipient..." : "Add more..."} 
                        value={newRecipient} 
                        onChange={e => { setNewRecipient(e.target.value); setShowContactDropdown(true); }}
                        onBlur={() => setTimeout(() => setShowContactDropdown(false), 200)}
                        style={{border: 'none', outline: 'none', flex: 1, minWidth: '150px', fontSize: '16px'}}
                      />
                   </div>
                   {showContactDropdown && newRecipient && matchedDropdownContacts.length > 0 && (
                     <div style={{position: 'relative'}}>
                        <div style={{position: 'absolute', top: 0, left: 0, right: 0, background: 'white', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', zIndex: 100, borderRadius: '8px', overflow: 'hidden'}}>
                           {matchedDropdownContacts.map(c => (
                             <div key={c.id} style={{padding: '12px 20px', cursor: 'pointer', borderBottom: '1px solid #f9f9f9'}} onClick={() => addRecipient(c.identifier)}>
                                <div style={{fontWeight: 'bold'}}>{c.name}</div>
                                <div style={{fontSize: '12px', color: '#999'}}>{c.identifier}</div>
                             </div>
                           ))}
                        </div>
                     </div>
                   )}
                   {activePlatform === 'email' && <input placeholder="Subject" value={subject} onChange={e => setSubject(e.target.value)} style={{width: '100%', padding: '12px 0', border: 'none', borderBottom: '2px solid #eee', fontSize: '16px', outline: 'none', marginBottom: '15px'}} />}
                   <textarea placeholder="Write your message..." value={inputText} onChange={e => setInputText(e.target.value)} style={{width: '100%', minHeight: '200px', border: 'none', fontSize: '15px', outline: 'none', resize: 'none'}} />
                   {mediaUrl && (
                      <div style={{padding: '10px', background: '#f5f5f5', borderRadius: '8px', marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px'}}>
                         <span>📎</span>
                         <span style={{fontSize: '13px'}}>File Attached</span>
                         <span style={{marginLeft: 'auto', cursor: 'pointer'}} onClick={() => setMediaUrl(null)}>✕</span>
                      </div>
                   )}
                   <div style={{display: 'flex', justifyContent: 'flex-end', gap: '15px', borderTop: '1px solid #eee', paddingTop: '20px', alignItems: 'center'}}>
                      <label style={{cursor: 'pointer', fontSize: '20px'}}><input type="file" style={{display: 'none'}} onChange={handleFileUpload} />📎</label>
                      <button onClick={sendMessage} className="compose-btn" style={{width: 'auto', padding: '10px 40px', margin: 0}}>Send</button>
                   </div>
                </div>
             </div>
          </div>
        ) : selectedContact ? (
          <>
            <div className="chat-header" style={{background: activePlatform === 'whatsapp' ? '#075e54' : '#1a73e8'}}>
               <Avatar name={selectedContact.contact_name || selectedContact.contact_identifier} size={40} />
               <div style={{flex: 1}}>
                  <div style={{fontWeight: 'bold'}}>{selectedContact.contact_name || selectedContact.contact_identifier}</div>
                  <div style={{fontSize: '11px', opacity: 0.8}}>{activePlatform === 'whatsapp' ? 'online' : selectedContact.contact_identifier}</div>
               </div>
            </div>
            <div className="messages-container" style={{background: activePlatform === 'whatsapp' ? 'var(--wa-bg)' : 'white'}}>
              {activePlatform === 'whatsapp' ? (
                messages.map(msg => (
                  <div key={msg.id} className={`message whatsapp-${msg.direction}`} onDoubleClick={() => setReplyingTo(msg)} style={{alignSelf: msg.direction === 'outbound' ? 'flex-end' : 'flex-start'}}>
                    {msg.reply_to && <div className="wa-reply-preview" style={{borderLeftColor: '#06cf9c'}}><div style={{fontWeight: 'bold', color: '#06cf9c'}}>You</div><div>{messages.find(m => m.id === msg.reply_to)?.body || 'Reply context...'}</div></div>}
                    {msg.media_url && <img src={msg.media_url} alt="Media" style={{maxWidth: '100%', borderRadius: '4px', marginBottom: '4px'}} />}
                    <div>{msg.body}</div>
                    <div style={{fontSize: '10px', textAlign: 'right', opacity: 0.6, marginTop: '4px', display: 'flex', justifyContent: 'flex-end', gap: '4px'}}>
                      {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                      {msg.direction === 'outbound' && getTicks(msg.status)}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{padding: '20px'}}>
                   <h2 style={{fontWeight: 400, marginBottom: '30px'}}>{messages[0]?.subject || '(No Subject)'}</h2>
                   {messages.map(msg => (
                     <div key={msg.id} className="email-thread-card">
                        <div style={{padding: '15px 20px', display: 'flex', justifyContent: 'space-between', background: '#f8f9fa', borderRadius: '8px 8px 0 0'}}>
                           <strong>{msg.direction === 'outbound' ? 'me' : selectedContact.contact_identifier}</strong>
                           <div style={{display: 'flex', alignItems: 'center', gap: '15px'}}>
                              <span style={{color: '#999', fontSize: '12px'}}>{new Date(msg.timestamp).toLocaleString()}</span>
                              <span className={`star-icon ${msg.is_starred ? 'active' : 'inactive'}`} onClick={() => toggleStar(msg.id)}>★</span>
                           </div>
                        </div>
                        <div style={{padding: '25px', fontSize: '14px', lineHeight: 1.6}}>{msg.body}</div>
                        <div style={{padding: '10px 20px', borderTop: '1px solid #eee', display: 'flex', gap: '15px'}}>
                           <button onClick={() => setReplyingTo(msg)} style={{background: 'none', border: '1px solid #ddd', borderRadius: '15px', padding: '5px 15px', fontSize: '12px', cursor: 'pointer'}}>Reply</button>
                        </div>
                     </div>
                   ))}
                </div>
              )}
              {activePlatform === 'whatsapp' && showAttachMenu && (
                <div className="wa-attach-menu">
                   <label className="wa-attach-item"><input type="file" style={{display: 'none'}} onChange={handleFileUpload} /><div className="wa-attach-icon" style={{background: '#bf59cf'}}>🖼️</div>Gallery</label>
                   <label className="wa-attach-item"><input type="file" style={{display: 'none'}} onChange={handleFileUpload} /><div className="wa-attach-icon" style={{background: '#7f66ff'}}>📄</div>Document</label>
                   <label className="wa-attach-item"><input type="file" accept="image/*" capture="camera" style={{display: 'none'}} onChange={handleFileUpload} /><div className="wa-attach-icon" style={{background: '#ff2e74'}}>📸</div>Camera</label>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* FIX: Reply Indicator Bar */}
            {replyingTo && (
              <div className="reply-indicator-bar">
                <div style={{minWidth: 0}}>
                  <div style={{fontWeight: 'bold', color: activePlatform === 'whatsapp' ? '#00a884' : '#1a73e8'}}>Replying to {replyingTo.direction === 'outbound' ? 'Yourself' : (selectedContact.contact_name || selectedContact.contact_identifier)}</div>
                  <div style={{whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', opacity: 0.7}}>{replyingTo.body || replyingTo.subject || 'Media...'}</div>
                </div>
                <div style={{cursor: 'pointer', fontSize: '18px', padding: '0 10px'}} onClick={() => setReplyingTo(null)}>✕</div>
              </div>
            )}

            <div style={{padding: '10px 20px', background: '#f0f2f5'}}>
               {mediaUrl && <div style={{padding: '10px', background: 'white', borderRadius: '8px', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '10px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)'}}><span>📎</span><img src={mediaUrl} alt="Attached" style={{height: '40px', borderRadius: '4px'}} /><span style={{marginLeft: 'auto', cursor: 'pointer'}} onClick={() => setMediaUrl(null)}>✕</span></div>}
               <div style={{display: 'flex', gap: '15px', alignItems: 'center'}}>
                  <div style={{fontSize: '24px', cursor: 'pointer', color: '#666'}} onClick={() => setShowAttachMenu(!showAttachMenu)}>{activePlatform === 'whatsapp' ? '+' : '📎'}</div>
                  <input 
                    placeholder="Type a message" 
                    value={inputText} 
                    onChange={e => setInputText(e.target.value)} 
                    onKeyDown={e => e.key === 'Enter' && sendMessage()} // FIX: onKeyDown instead of onKeyPress
                    style={{flex: 1, padding: '10px 15px', borderRadius: '20px', border: 'none', outline: 'none'}} 
                  />
                  <button onClick={sendMessage} style={{background: activePlatform === 'whatsapp' ? '#00a884' : '#1a73e8', color: 'white', border: 'none', padding: '8px 25px', borderRadius: '20px', cursor: 'pointer', fontWeight: 'bold'}}>Send</button>
               </div>
            </div>
          </>
        ) : (
          <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f2f5'}}>
             <div style={{textAlign: 'center', opacity: 0.5}}>
                <div style={{fontSize: '80px'}}>{activePlatform === 'whatsapp' ? '📱' : '📧'}</div>
                <h2>Enter the {activePlatform === 'whatsapp' ? 'WhatsApp' : 'Gmail'} World</h2>
                <p>Pick a conversation to start messaging.</p>
             </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
