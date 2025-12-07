import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <Card className="w-[400px]">
        <CardHeader>
          <CardTitle>Antigravity Dev</CardTitle>
          <CardDescription>
            AI-Powered Development Platform
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button className="w-full">
            Enter Mission Control
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
