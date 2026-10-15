// Adapted from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See
// LICENSES/laravel-react-starter-kit.md. Drops the kit's passkey confirmation UI (Phase 5,
// D-009).
import { Form, Head } from "@inertiajs/react";
import InputError from "@/components/input-error";
import PasswordInput from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { store } from "@/routes/password/confirm";

export default function ConfirmPassword() {
    return (
        <>
            <Head title="Confirm password" />

            <Form {...store.form()} resetOnSuccess={["password"]}>
                {({ processing, errors }) => (
                    <div className="space-y-6">
                        <div className="grid gap-2">
                            <Label htmlFor="password">Password</Label>
                            <PasswordInput
                                id="password"
                                name="password"
                                placeholder="Password"
                                autoComplete="current-password"
                                autoFocus
                            />

                            <InputError message={errors.password} />
                        </div>

                        <div className="flex items-center">
                            <Button
                                className="w-full"
                                disabled={processing}
                                data-test="confirm-password-button"
                            >
                                {processing && <Spinner />}
                                Confirm password
                            </Button>
                        </div>
                    </div>
                )}
            </Form>
        </>
    );
}

ConfirmPassword.layout = {
    title: "Confirm password",
    description:
        "This is a secure area of the application. Please confirm your password before continuing.",
};
