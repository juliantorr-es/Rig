private func unusedPrivateFunc() {
    print("I am dead")
}

public func publicApiProtected() {
    print("I am alive")
}

struct UnusedType {
    let x: Int
    var y: String = ""
}

class ReferencedType {
    static let shared = ReferencedType()
}

let topLevelUnused = 42

func referencedFunc() {
    _ = ReferencedType.shared
}
