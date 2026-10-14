import { Form, Link } from "@inertiajs/react";

export default function Create() {
  return (
    <div>
      <h1>Create post</h1>
      <Form action="/posts" method="post">
        {({ errors, processing }) => (
          <>
            <input name="title" data-testid="title" />
            {errors.title && <p data-testid="error-title">{errors.title}</p>}
            <button type="submit" disabled={processing} data-testid="submit">Save</button>
          </>
        )}
      </Form>
      <Link href="/posts" data-testid="to-index">Index</Link>
    </div>
  );
}
