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

interface LogicalModelsFormProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function LogicalModelsForm({ open, onOpenChange }: LogicalModelsFormProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Create Logical Model</DialogTitle>
                    <DialogDescription>
                        Map a logical model name to physical model implementations
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Logical Model Name</label>
                        <Input placeholder="e.g., gpt-4-turbo" />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Provider</label>
                        <Input placeholder="e.g., OpenAI" />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Physical Model ID</label>
                        <Input placeholder="e.g., gpt-4-turbo-2024-04-09" />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={() => onOpenChange(false)}>Create Model</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
