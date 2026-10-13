// Copy into a pinned HAI backend/internal/accountfeed checkout and run:
// AUTOPOSTER_HAI_EXPORT_PATH=/absolute/feed.json go test ./internal/accountfeed -run TestAutoposterExport -v
// This exercises HAI's real parser and in-memory ingestion, not a substitute parser.
package accountfeed

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"automation-hub-backend/internal/operations"
	"automation-hub-backend/internal/privacyfilter"
)

func TestAutoposterExport(t *testing.T) {
	path := os.Getenv("AUTOPOSTER_HAI_EXPORT_PATH")
	if path == "" {
		t.Fatal("AUTOPOSTER_HAI_EXPORT_PATH must name an actual Autoposter download containing one HAI consumer chair")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := ParseGenericFeed(raw, 0, 0)
	if err != nil || len(parsed.Items) != 1 {
		t.Fatalf("expected one valid exported item: items=%d error=%v", len(parsed.Items), err)
	}
	item := parsed.Items[0]
	if item.Title != "HAI consumer chair" || item.Provider != "generic_json_feed" || item.ItemType != "document" {
		t.Fatalf("incorrect exported item contract: %+v", item)
	}
	if item.Metadata["execution_authority"] != false {
		t.Fatal("export must not grant execution authority")
	}
	ops := operations.NewService(operations.NewMemoryRepository())
	registry := NewRegistry(ops, privacyfilter.NewService(), FetchOptions{FeedsRoot: filepath.Dir(path)})
	feed, err := registry.Register(Feed{
		Name: "Autoposter contract verification", Provider: "generic_json_feed",
		SourceType: SourceLocalJSONFile, Path: filepath.Base(path),
		OwnerUserID: "isolated-contract-owner", AccountLabel: "isolated-autoposter",
		WorkspaceID: "local", Enabled: true,
	})
	if err != nil {
		t.Fatal(err)
	}
	first, ok := registry.Sync(context.Background(), feed.ID)
	if !ok || len(first.Errors) != 0 || first.ItemsRead != 1 || first.OperationsCreated != 1 {
		t.Fatalf("actual HAI ingestion failed: %+v", first)
	}
	replay, ok := registry.Sync(context.Background(), feed.ID)
	if !ok || len(replay.Errors) != 0 || replay.ItemsRead != 1 || replay.OperationsCreated != 0 || replay.OperationsRefresh != 1 {
		t.Fatalf("actual HAI replay was not deduplicated: %+v", replay)
	}
	old, err := ParseGenericFeed([]byte(`{"records":[{"id":"listing:1","title":"Old incompatible envelope"}]}`), 0, 0)
	if err != nil || len(old.Items) != 0 {
		t.Fatalf("pinned parser's old-envelope behavior changed: items=%d error=%v", len(old.Items), err)
	}
	t.Log("PASS: actual Autoposter download parsed, ingested once, and replay-deduplicated by HAI")
}
