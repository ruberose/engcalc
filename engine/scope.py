"""
수식 블록들이 공유하는 변수 저장소.

DocumentScene이 문서 전체를 재계산할 때마다 새 Scope를 만들고,
위(y좌표)에서 아래로 블록을 하나씩 evaluate()하면서 채워 나간다.
이후 블록은 그 이전 블록들이 채워둔 변수를 그대로 참조할 수 있다.
"""

from typing import Any


class Scope:
    """변수 이름 -> 값 매핑."""

    def __init__(self) -> None:
        self._variables: dict[str, Any] = {}

    def get(self, name: str) -> Any:
        """변수 값을 가져온다. 정의되어 있지 않으면 None."""
        return self._variables.get(name)

    def set(self, name: str, value: Any) -> None:
        """변수 값을 등록하거나 덮어쓴다."""
        self._variables[name] = value

    def has(self, name: str) -> bool:
        """해당 이름의 변수가 정의되어 있는지 확인한다."""
        return name in self._variables

    def as_dict(self) -> dict[str, Any]:
        """SymPy 파서의 local_dict 등에 바로 넘길 수 있는 사본을 반환한다."""
        return dict(self._variables)

    def clear(self) -> None:
        """모든 변수를 지운다 (전체 재계산을 새로 시작할 때 사용)."""
        self._variables.clear()
