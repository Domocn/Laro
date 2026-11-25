import pytest

from services.drive_import import DriveImportError, drive_file_id
from services.recipe_pdf_import import group_pages_at_recipe_starts, page_starts_recipe

FILE_ID = "1F8DyHZsXNwpQp_Bl7tQRcU4IDp-cJ27R"


@pytest.mark.parametrize(
    "url",
    [
        f"https://drive.google.com/file/d/{FILE_ID}/view?usp=drivesdk",
        f"https://drive.google.com/open?id={FILE_ID}",
        f"https://drive.google.com/uc?export=download&id={FILE_ID}",
    ],
)
def test_drive_file_id_from_share_links(url):
    assert drive_file_id(url) == FILE_ID


@pytest.mark.parametrize(
    "url",
    ["https://evil.example.com/file/d/" + FILE_ID, "http://169.254.169.254/latest", "not a link", ""],
)
def test_drive_file_id_rejects_other_hosts(url):
    with pytest.raises(DriveImportError):
        drive_file_id(url)


def _recipe_page(title):
    return f"14 {title} 150g dry red lentils 360ml hot water " + "method words " * 40


def test_page_starts_recipe():
    assert page_starts_recipe(_recipe_page("RED LENTIL WRAPS WITH LEMONGRASS TOFU"))
    assert page_starts_recipe("LEFT: Creamy Polenta " + _recipe_page("CREAMY POLENTA WITH BEANS"))
    assert not page_starts_recipe("15 Red Lentil Wraps: Place the lentils in 200g water " + "and stir " * 60)
    assert not page_starts_recipe("Short intro page")


def test_groups_only_break_at_recipe_starts():
    filler = "continued method text 100g " + "stir it " * 60
    pages = ["intro"] * 3 + [_recipe_page("FIRST DISH")] + [filler] * 5 + [_recipe_page("SECOND DISH")] + [filler] * 8 + [_recipe_page("THIRD DISH")] + [filler]
    groups = group_pages_at_recipe_starts(pages, max_pages=10)
    starts = {i for i, p in enumerate(pages) if page_starts_recipe(p)}
    assert groups[0][0] == 0 and groups[-1][1] == len(pages)
    for (a, b), (c, _d) in zip(groups, groups[1:]):
        assert b == c and c in starts  # every cut lands on a recipe's first page


def test_running_job_is_reused_until_done():
    import asyncio
    import services.drive_import as di

    di._redis = False  # memory store
    di._memory_jobs.clear()

    async def flow():
        job = di.new_job("u1", FILE_ID)
        await di.save_job(job)
        await di.mark_running(job)
        assert (await di.find_running_job("u1", FILE_ID))["id"] == job["id"]
        assert await di.find_running_job("u2", FILE_ID) is None
        job["status"] = "done"
        await di.save_job(job)
        assert await di.find_running_job("u1", FILE_ID) is None

    asyncio.run(flow())
