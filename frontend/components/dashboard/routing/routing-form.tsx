"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

interface RoutingFormProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function RoutingForm({ open, onOpenChange }: RoutingFormProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Create Routing Rule</DialogTitle>
                    <DialogDescription>
                        Configure a new routing strategy for model requests
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Rule Name</label>
                        <Input placeholder="e.g., Load Balance GPT-4" />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Strategy</label>
                        <Input placeholder="e.g., Round Robin, Fallback, Weighted" />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Models (comma-separated)</label>
                        <Input placeholder="e.g., gpt-4-turbo, gpt-4" />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Weight/Config</label>
                        <Input placeholder="e.g., 50/50 or Primary/Backup" />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={() => onOpenChange(false)}>Create Rule</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
