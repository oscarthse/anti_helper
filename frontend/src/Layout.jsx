import React from 'react';

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-zinc-950">
      <style>{`
        :root {
          --background: 9 9 11;
          --foreground: 244 244 245;
          --card: 24 24 27;
          --card-foreground: 244 244 245;
          --popover: 24 24 27;
          --popover-foreground: 244 244 245;
          --primary: 59 130 246;
          --primary-foreground: 255 255 255;
          --secondary: 39 39 42;
          --secondary-foreground: 244 244 245;
          --muted: 39 39 42;
          --muted-foreground: 161 161 170;
          --accent: 39 39 42;
          --accent-foreground: 244 244 245;
          --destructive: 239 68 68;
          --destructive-foreground: 255 255 255;
          --border: 39 39 42;
          --input: 39 39 42;
          --ring: 59 130 246;
        }
        
        * {
          scrollbar-width: thin;
          scrollbar-color: rgb(63 63 70) transparent;
        }
        
        *::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        
        *::-webkit-scrollbar-track {
          background: transparent;
        }
        
        *::-webkit-scrollbar-thumb {
          background-color: rgb(63 63 70);
          border-radius: 3px;
        }
        
        *::-webkit-scrollbar-thumb:hover {
          background-color: rgb(82 82 91);
        }
        
        body {
          background-color: rgb(9 9 11);
          color: rgb(244 244 245);
        }
        
        ::selection {
          background-color: rgb(59 130 246 / 0.3);
        }
      `}</style>
      {children}
    </div>
  );
}