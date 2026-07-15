"""ALIO 기관별 내부규정 첨부파일 다운로드 프로그램."""

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    raise SystemExit(
        "Playwright가 설치되어 있지 않습니다. "
        "'pip install playwright' 실행 후 "
        "'playwright install chromium'을 실행하세요."
    ) from exc
import re
import os

def extract_fileno(href):
    """href에서 fileNo 값을 추출"""
    if not href:
        return 0
    match = re.search(r'fileNo=(\d+)', href)
    return int(match.group(1)) if match else 0


def select_preferred_download_link(bt_list, preferred_extensions):
    """선호 확장자와 fileNo를 기준으로 다운로드 링크 하나를 선택"""
    links = bt_list.locator('p a')
    candidates = []

    for index in range(links.count()):
        link = links.nth(index)
        href = link.get_attribute('href') or ''
        link_text = link.inner_text().strip()
        extension = os.path.splitext(link_text)[1].lower()

        try:
            extension_rank = preferred_extensions.index(extension)
        except ValueError:
            extension_rank = len(preferred_extensions)

        candidates.append({
            'index': index,
            'link': link,
            'text': link_text,
            'file_no': extract_fileno(href),
            'extension_rank': extension_rank,
        })

    if not candidates:
        return None

    # PDF > HWPX > HWP 순으로 우선하며, 같은 형식이면 큰 fileNo를 선택한다.
    return min(
        candidates,
        key=lambda item: (
            item['extension_rank'],
            -item['file_no'],
            item['index'],
        ),
    )


def scrape_alio_data(
    target_org_list,
    base_download_dir=r"C:\ALIO_Data\new",
    preferred_extensions=('.pdf', '.hwpx', '.hwp'),
):
    """
    ALIO 웹사이트에서 지정된 기관들의 문서를 스크래핑
    
    Args:
        target_org_list: 스크래핑할 기관명 리스트
        base_download_dir: 기본 다운로드 경로
    """
    # 기본 다운로드 디렉토리 생성
    os.makedirs(base_download_dir, exist_ok=True)
    print(f"기본 다운로드 경로: {base_download_dir}\n")
    
    # 진행 상황 파일 경로
    progress_file = os.path.join(base_download_dir, "진행상황.txt")
    completed_orgs = set()
    
    # 이전 진행 상황 로드
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            completed_orgs = set(line.strip() for line in f if line.strip())
        print(f"이전 진행 상황 로드: {len(completed_orgs)}개 기관 완료됨")
        print(f"남은 기관: {len(target_org_list) - len(completed_orgs)}개\n")
    
    with sync_playwright() as p:
        # 브라우저 실행
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            accept_downloads=True  # 다운로드 허용
        )
        page = context.new_page()
        
        # 페이지 접속
        url = "https://www.alio.go.kr/item/itemOrganList.do?reportFormRootNo=21110"
        page.goto(url, wait_until='domcontentloaded')
        page.locator('select.form-control').wait_for(state='attached')
        
        successful_orgs = 0
        failed_orgs = 0
        skipped_orgs = 0

        # 각 기관별로 반복
        for org_index, org_name in enumerate(target_org_list, 1):
            # 이미 완료된 기관은 건너뛰기
            if org_name in completed_orgs:
                skipped_orgs += 1
                print(f"\n[{org_index}/{len(target_org_list)}] {org_name} - 이미 완료됨, 건너뛰기")
                continue
            
            print(f"\n{'='*50}")
            print(f"[{org_index}/{len(target_org_list)}] 기관 처리 시작: {org_name}")
            print(f"{'='*50}")
            
            # 기관별 폴더 생성
            org_download_dir = os.path.join(base_download_dir, org_name)
            os.makedirs(org_download_dir, exist_ok=True)
            print(f"다운로드 폴더 생성: {org_download_dir}\n")
            
            try:
                failed_items = 0

                # 1. 기관명 선택
                print("1. 기관명 선택...")
                select_element = page.locator('select.form-control')
                if select_element.count() != 1:
                    print("검색 창을 찾을 수 없습니다.")
                    continue

                selected_values = select_element.select_option(label=org_name)
                if not selected_values:
                    raise RuntimeError(f"기관을 선택할 수 없습니다: {org_name}")
                print(f"2. 기관 '{org_name}' 선택 완료")
                
                # 3. 조회 버튼 클릭
                print("3. 조회 버튼 클릭...")
                query_button = page.get_by_role('button', name='조회', exact=True)
                if query_button.count() != 1:
                    raise RuntimeError("조회 버튼을 정확히 하나 찾지 못했습니다.")

                with page.expect_response(
                    lambda response: '/item/itemReportListSusi.json' in response.url,
                    timeout=15_000,
                ) as response_info:
                    query_button.click()

                response = response_info.value
                if not response.ok:
                    raise RuntimeError(f"기관 조회 실패: HTTP {response.status}")
                
                # 페이지별 처리
                total_downloaded = 0
                visited_pages = set()
                
                while True:
                    active_page = page.locator('.paging a.active')
                    if active_page.count() == 1:
                        current_page = int(active_page.inner_text().strip())
                    else:
                        current_page = 1

                    if current_page in visited_pages:
                        raise RuntimeError(f"페이지 {current_page}를 다시 방문했습니다.")
                    visited_pages.add(current_page)

                    print(f"\n--- 페이지 {current_page} 처리 중 ---")
                    
                    # 4. 현재 페이지의 항목 가져오기
                    item_locator = page.locator('.list-inner2 ul li')
                    li_count = item_locator.count()

                    if li_count == 0:
                        print("더 이상 항목이 없습니다. 다음 기관으로 이동...")
                        break

                    print(f"현재 페이지 li 개수: {li_count}")

                    # 각 항목 처리
                    for i in range(li_count):
                        popup = None
                        try:
                            print(f"\n  페이지 {current_page}의 {i + 1}번째 항목 처리 중...")

                            # DOM 갱신에 대비해 항목과 링크를 매번 다시 찾는다.
                            li_element = page.locator('.list-inner2 ul li').nth(i)
                            link_in_li = li_element.locator('a[href="javascript:void(0);"]')
                            if link_in_li.count() != 1:
                                raise RuntimeError("상세 링크를 정확히 하나 찾지 못했습니다.")

                            # 5. 실제 링크를 클릭하고 새 창을 기다린다.
                            print("    5. 상세 링크 클릭 후 팝업 대기...")
                            with page.expect_popup(timeout=15_000) as popup_info:
                                link_in_li.click()

                            popup = popup_info.value
                            popup.wait_for_load_state('domcontentloaded')
                            print("    팝업 창 열림")

                            # 6. 팝업 창의 다운로드 링크 영역을 명시적으로 기다린다.
                            print("    6. 다운로드 링크 영역 확인...")
                            bt_list = popup.locator('.bt-list')
                            bt_list.wait_for(state='visible', timeout=15_000)

                            # 7. 확장자 우선순위에 따라 파일 하나를 선택한다.
                            selected = select_preferred_download_link(
                                bt_list,
                                preferred_extensions,
                            )
                            if selected is None:
                                raise RuntimeError("다운로드 링크를 찾을 수 없습니다.")

                            print(
                                "    7. 선택된 파일: "
                                f"{selected['text']} (fileNo: {selected['file_no']})"
                            )

                            # 8. 다운로드가 실제 완료된 경우에만 성공 건수를 증가시킨다.
                            with popup.expect_download(timeout=15_000) as download_info:
                                selected['link'].click()

                            download = download_info.value
                            filename = f"{total_downloaded + 1}_{download.suggested_filename}"
                            filepath = os.path.join(org_download_dir, filename)
                            download.save_as(filepath)
                            total_downloaded += 1
                            print(f"    ✓ 저장 완료: {filename}\n")

                        except Exception as e:
                            failed_items += 1
                            print(f"    ✗ 항목 처리 중 오류: {e}")
                            try:
                                screenshot_path = os.path.join(
                                    org_download_dir,
                                    f"error_page_{current_page}_item_{i + 1}.png",
                                )
                                screenshot_target = (
                                    popup
                                    if popup is not None and not popup.is_closed()
                                    else page
                                )
                                screenshot_target.screenshot(path=screenshot_path)
                                print(f"    오류 스크린샷 저장: {screenshot_path}")
                            except Exception as screenshot_error:
                                print(f"    스크린샷 저장 실패: {screenshot_error}")
                        finally:
                            if popup is not None and not popup.is_closed():
                                popup.close()
                    
                    # 페이지 크기가 아니라 실제 다음 페이지 링크의 존재 여부로 판단한다.
                    paging = page.locator('.paging')
                    if paging.count() != 1:
                        print("더 이상 페이지가 없습니다.")
                        break

                    next_page_num = current_page + 1
                    next_page_link = paging.get_by_role(
                        'link',
                        name=str(next_page_num),
                        exact=True,
                    )
                    next_group_button = paging.locator('a.nxt-bt')

                    if next_page_link.count() == 1 and next_page_link.is_visible():
                        page_move_target = next_page_link
                    elif (
                        next_group_button.count() == 1
                        and next_group_button.is_visible()
                    ):
                        page_move_target = next_group_button
                    else:
                        print("더 이상 페이지가 없습니다.")
                        break

                    print(f"페이지 {next_page_num}으로 이동...")
                    with page.expect_response(
                        lambda response: '/item/itemReportListSusi.json' in response.url,
                        timeout=15_000,
                    ) as response_info:
                        page_move_target.click()

                    response = response_info.value
                    if not response.ok:
                        raise RuntimeError(
                            f"페이지 {next_page_num} 조회 실패: HTTP {response.status}"
                        )

                    page.wait_for_function(
                        """expected => {
                            const active = document.querySelector('.paging a.active');
                            return active && Number(active.textContent.trim()) === expected;
                        }""",
                        arg=next_page_num,
                        timeout=10_000,
                    )

                print(f"\n{org_name} 처리 결과: 총 {total_downloaded}개 다운로드")
                print(f"  저장 위치: {org_download_dir}")

                # 항목 하나라도 실패하면 다음 실행에서 다시 시도하도록 완료 기록을 남기지 않는다.
                if failed_items == 0:
                    with open(progress_file, 'a', encoding='utf-8') as f:
                        f.write(f"{org_name}\n")
                    completed_orgs.add(org_name)
                    successful_orgs += 1
                    print("  ✓ 모든 항목 처리 완료")
                else:
                    failed_orgs += 1
                    print(
                        f"  ✗ {failed_items}개 항목 실패 - 완료 목록에 기록하지 않음"
                    )
             
            except Exception as e:
                failed_orgs += 1
                print(f"✗ 기관 '{org_name}' 처리 중 오류 발생: {e}")
                print("  완료 목록에 기록하지 않았습니다. 다음 실행에서 다시 시도합니다.")
                continue
        
        print("\n" + "="*70)
        print(f"{'기관 처리 종료':^70}")
        print(f"이번 실행 성공: {successful_orgs}개 기관")
        print(f"이번 실행 실패 또는 일부 실패: {failed_orgs}개 기관")
        print(f"이전에 완료되어 건너뜀: {skipped_orgs}개 기관")
        print(f"다운로드 위치: {base_download_dir}")
        print("="*70)
        
        browser.close()
        print("\n프로그램을 종료합니다.")


if __name__ == "__main__":
    import csv
    
    # TXT 또는 CSV 파일에서 읽기
    txt_file = r"C:\ALIO_Data\알리오 공공기관 다운로드 리스트.txt"
    csv_file = r"C:\ALIO_Data\알리오 공공기관 다운로드 리스트.csv"
    
    target_org_list = []
    
    # 우선순위: TXT > CSV > 기본 리스트
    if os.path.exists(txt_file):
        print(f"TXT 파일에서 기관 목록 로드: {txt_file}")
        with open(txt_file, 'r', encoding='utf-8') as f:
            target_org_list = [line.strip() for line in f if line.strip()]
        print(f"총 {len(target_org_list)}개 기관 로드됨")
    
    elif os.path.exists(csv_file):
        print(f"CSV 파일에서 기관 목록 로드: {csv_file}")
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # 헤더 건너뛰기
            for row in reader:
                if row:  # 빈 행이 아니면
                    target_org_list.append(row[0].strip())
        print(f"총 {len(target_org_list)}개 기관 로드됨")
    
    else:
        # TXT/CSV 파일이 없으면 기본 리스트 사용
        print("TXT/CSV 파일이 없습니다. 기본 리스트 사용")
        target_org_list = [
            # 여기에 더 많은 기관명 추가 가능
        ]
    
    scrape_alio_data(target_org_list)
