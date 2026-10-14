import { Deferred, Link, useHttp, usePage } from "@inertiajs/react";

type Post = { id: number; title: string };

function PostList() {
  const { posts } = usePage<{ posts: Post[] }>().props;
  return <ul data-testid="posts">{posts.map((p) => <li key={p.id}>{p.title}</li>)}</ul>;
}

export default function Index() {
  const page = usePage();
  const flash = (page as any).flash as { success?: string } | undefined;
  const http = useHttp({});
  return (
    <div>
      <h1>Posts</h1>
      {flash?.success && <p data-testid="flash">{flash.success}</p>}
      <Deferred data="posts" fallback={<p data-testid="loading">Loading…</p>}>
        <PostList />
      </Deferred>
      <button
        data-testid="stats"
        onClick={async () => {
          const data: any = await http.get("/stats");
          (document.getElementById("count") as HTMLElement).textContent = `count: ${data.count}`;
        }}
      >
        Stats
      </button>
      <p id="count" data-testid="count"></p>
      <Link href="/posts/create" data-testid="to-create">Create</Link>
    </div>
  );
}
